"""This file and its contents are licensed under the Apache License 2.0. Please see the included NOTICE for copyright information and LICENSE for a copy of the license.
"""
import logging
from datetime import datetime

from core.feature_flags import flag_set
from core.permissions import AllPermissions
from core.redis import start_job_async_or_sync
from core.utils.common import load_func
from data_manager.actions import DataManagerAction
from data_manager.functions import evaluate_predictions
from django.conf import settings
from projects.models import Project
from tasks.functions import update_tasks_counters
from tasks.models import Annotation, AnnotationDraft, Prediction, Task
from users.models import User
from webhooks.models import WebhookAction
from webhooks.utils import emit_webhooks_for_instance

all_permissions = AllPermissions()
logger = logging.getLogger(__name__)


def retrieve_tasks_predictions(project, queryset, **kwargs):
    """Retrieve predictions by tasks ids

    Sends the tasks to the project's ML backend, which runs the model and returns
    predictions. Label Studio saves them on the tasks.

    [DFO progress patch] The web page now calls this for 10 tasks at a time (see
    invokeActionInBatches in web/libs/datamanager/src/stores/AppStore.js) instead of once
    for the whole selection. The response also gains "created", "with_predictions" and
    "model_version", which the progress dialog uses. "processed_items" and "detail" are
    unchanged, so existing API users are not affected.

    :param project: project instance
    :param queryset: filtered tasks db queryset
    """
    # evaluate_predictions() -> MLBackend.predict_tasks(). Its return value says what
    # happened: a list of the Prediction objects it saved, the model version string if
    # every task already had a prediction from that version, or None if the backend
    # isn't ready. Stock Label Studio ignored it.
    result = evaluate_predictions(queryset)
    count = queryset.count()
    response = {'processed_items': count, 'detail': 'Retrieved ' + str(count) + ' predictions'}
    response.update(_prediction_counts(project, queryset, result))
    return response


def _prediction_counts(project, queryset, result):
    """[DFO progress patch] Report what Retrieve Predictions actually did.

    Stock Label Studio answers "Retrieved N predictions" whatever happened:
    predict_tasks() silently skips tasks that already have a prediction from the current
    model version, and when the ML backend errors it logs the error and saves nothing.
    Counting afterwards tells those cases apart:

    * created: predictions saved by this call
    * with_predictions: tasks that now have a prediction from the current model version
      (new ones plus ones that were skipped because they already had one)

    The web page derives: skipped = with_predictions - created, and
    missing = tasks sent - with_predictions (no boxes above the threshold, or a backend error).

    :param project: project instance
    :param queryset: the tasks that were sent to the ML backend
    :param result: what evaluate_predictions() returned (see retrieve_tasks_predictions)
    :return: dict with created, with_predictions and model_version
    """
    # A fresh query, so model_version is the one predict_tasks() just saved
    backend = project.ml_backend
    if not backend:
        return {'created': 0, 'with_predictions': 0, 'model_version': None}

    # Only a list means predictions were saved; a string or None means none were
    created = len(result) if isinstance(result, list) else 0

    # distinct(): the join on predictions would otherwise count a task once per prediction
    with_predictions = (
        Task.objects.filter(id__in=queryset.values('id'), predictions__model_version=backend.model_version)
        .distinct()
        .count()
    )
    return {'created': created, 'with_predictions': with_predictions, 'model_version': backend.model_version}


def selected_task_ids(project, queryset, **kwargs):
    """Return the IDs of the tasks selected in the Data Manager.

    Hidden helper used by the Retrieve Predictions progress dialog: it resolves the
    selection (including "select all" with filters and exclusions) once, then sends the
    tasks to the ML backend in small batches so it can show progress and avoid the
    request timeout that one large Retrieve Predictions call can hit.
    """
    # The queryset arrives already filtered by ProjectActionsAPI.post() from the request
    # body (selectedItems, filters), the same way as for every other action. Sorting by
    # ID makes batches go down the table in a stable order.
    task_ids = list(queryset.order_by('id').values_list('id', flat=True))
    return {'task_ids': task_ids, 'total': len(task_ids)}


def delete_tasks(project, queryset, **kwargs):
    """Delete tasks by ids

    :param project: project instance
    :param queryset: filtered tasks db queryset
    """
    tasks_ids = list(queryset.values('id'))
    count = len(tasks_ids)
    tasks_ids_list = [task['id'] for task in tasks_ids]
    project_count = project.tasks.count()
    # unlink tasks from project
    queryset = Task.objects.filter(id__in=tasks_ids_list)
    queryset.update(project=None)
    # delete all project tasks
    if count == project_count:
        start_job_async_or_sync(Task.delete_tasks_without_signals_from_task_ids, tasks_ids_list, queue_name='low')
        logger.info(f'calling reset project_id={project.id} delete_tasks()')
        project.summary.reset()

    # delete only specific tasks
    else:
        # update project summary and delete tasks
        start_job_async_or_sync(async_project_summary_recalculation, tasks_ids_list, project.id)

    project.update_tasks_states(
        maximum_annotations_changed=False, overlap_cohort_percentage_changed=False, tasks_number_changed=True
    )
    # emit webhooks for project
    emit_webhooks_for_instance(project.organization, project, WebhookAction.TASKS_DELETED, tasks_ids)

    # remove all tabs if there are no tasks in project
    reload = False
    if not project.tasks.exists():
        project.views.all().delete()
        reload = True

    # Execute actions after delete tasks
    Task.after_bulk_delete_actions(tasks_ids_list, project)

    return {'processed_items': count, 'reload': reload, 'detail': 'Deleted ' + str(count) + ' tasks'}


def delete_tasks_annotations(project, queryset, **kwargs):
    """Delete all annotations and drafts by tasks ids

    :param project: project instance
    :param queryset: filtered tasks db queryset
    """
    request = kwargs['request']
    annotator_id = request.data.get('annotator')

    task_ids = queryset.values_list('id', flat=True)
    annotations = Annotation.objects.filter(task__id__in=task_ids)
    if annotator_id:
        annotations = annotations.filter(completed_by=int(annotator_id))

    # take only tasks where annotations are going to be deleted
    real_task_ids = set(list(annotations.values_list('task__id', flat=True)))
    annotations_ids = list(annotations.values('id'))
    # remove deleted annotations from project.summary
    project.summary.remove_created_annotations_and_labels(annotations)
    # also remove drafts for the task. This includes task and annotation level
    # drafts by design.
    drafts = AnnotationDraft.objects.filter(task__id__in=task_ids)
    if annotator_id:
        drafts = drafts.filter(user=int(annotator_id))
    project.summary.remove_created_drafts_and_labels(drafts)

    # count before delete to return the number of deleted items, not including cascade deletions
    count = annotations.count()
    annotations.delete()
    drafts.delete()  # since task-level annotation drafts will not have been deleted by CASCADE
    emit_webhooks_for_instance(project.organization, project, WebhookAction.ANNOTATIONS_DELETED, annotations_ids)
    request = kwargs['request']

    tasks = Task.objects.filter(id__in=real_task_ids)
    tasks.update(updated_at=datetime.now(), updated_by=request.user)
    # Update tasks counter and is_labeled. It should be a single operation as counters affect bulk is_labeled update
    project.update_tasks_counters_and_is_labeled(tasks_queryset=real_task_ids)

    # LSE postprocess
    postprocess = load_func(settings.DELETE_TASKS_ANNOTATIONS_POSTPROCESS)
    if postprocess is not None:
        tasks = Task.objects.filter(id__in=task_ids)
        postprocess(project, tasks, **kwargs)

    return {'processed_items': count, 'detail': 'Deleted ' + str(count) + ' annotations'}


def delete_tasks_annotations_form(user, project):
    annotator_ids = list(Annotation.objects.filter(project=project).values_list('completed_by', flat=True))
    draft_annotator_ids = list(AnnotationDraft.objects.filter(task__project=project).values_list('user', flat=True))
    users = User.objects.filter(id__in=annotator_ids + draft_annotator_ids)
    return [
        {
            'columnCount': 1,
            'fields': [
                {
                    'type': 'select',
                    'name': 'annotator',
                    'label': 'Annotator',
                    'options': [
                        {'value': str(user.id), 'label': user.get_full_name() or user.username or user.email}
                        for user in users
                    ],
                    'placeholder': 'All',
                    'searchable': True,
                }
            ],
        }
    ]


def delete_tasks_predictions(project, queryset, **kwargs):
    """Delete all predictions by tasks ids

    :param project: project instance
    :param queryset: filtered tasks db queryset
    """
    task_ids = queryset.values_list('id', flat=True)
    predictions = Prediction.objects.filter(task__id__in=task_ids)
    if flag_set('fflag_root_223_optimize_delete_predictions', organization=project.organization):
        real_task_ids = predictions.order_by().values_list('task_id', flat=True).distinct()
    else:
        real_task_ids = set(list(predictions.values_list('task_id', flat=True)))

    count = predictions.count()
    predictions.delete()
    start_job_async_or_sync(update_tasks_counters, Task.objects.filter(id__in=real_task_ids))
    return {'processed_items': count, 'detail': 'Deleted ' + str(count) + ' predictions'}


def async_project_summary_recalculation(tasks_ids_list, project_id):
    queryset = Task.objects.filter(id__in=tasks_ids_list)
    project = Project.objects.get(id=project_id)
    project.summary.remove_created_annotations_and_labels(Annotation.objects.filter(task__in=queryset))
    project.summary.remove_data_columns(queryset)
    Task.delete_tasks_without_signals(queryset)


actions: list[DataManagerAction] = [
    {
        'entry_point': retrieve_tasks_predictions,
        'permission': all_permissions.predictions_any,
        'title': 'Retrieve Predictions',
        'order': 90,
        'dialog': {
            'title': 'Retrieve Predictions',
            # [DFO progress patch] The stock text warned about timeouts and suggested the API
            # instead; batching removes that problem, so the text describes the progress bar.
            'text': 'Send the selected tasks to the ML backend connected to the project. '
            'Tasks are sent in small batches and a progress bar shows how many are done. '
            'Please confirm your action.',
            'type': 'confirm',
        },
    },
    # [DFO progress patch] Helper for the Retrieve Predictions progress dialog. The action ID
    # is the function name, "selected_task_ids". 'hidden': True keeps it out of the Actions
    # menu (get_all_actions() filters hidden actions), but it can still be called through
    # POST /api/dm/actions?id=selected_task_ids. It needs the same permission as Retrieve
    # Predictions, so only users who can retrieve predictions can call it.
    {
        'entry_point': selected_task_ids,
        'permission': all_permissions.predictions_any,
        'title': 'Selected task IDs',
        'order': 0,
        'hidden': True,
    },
    {
        'entry_point': delete_tasks,
        'permission': all_permissions.tasks_delete,
        'title': 'Delete Tasks',
        'order': 100,
        'reload': True,
        'dialog': {
            'text': 'You are going to delete the selected tasks. Please confirm your action.',
            'type': 'confirm',
        },
    },
    {
        'entry_point': delete_tasks_annotations,
        'permission': [all_permissions.tasks_change, all_permissions.annotations_delete],
        'title': 'Delete Annotations',
        'order': 101,
        'dialog': {
            'text': 'You are going to delete annotations from the selected tasks.\n'
            'You can select specific annotators to delete annotations for.\n'
            'Please confirm your action.',
            'type': 'confirm',
            'form': delete_tasks_annotations_form,
        },
    },
    {
        'entry_point': delete_tasks_predictions,
        'permission': all_permissions.predictions_any,
        'title': 'Delete Predictions',
        'order': 102,
        'dialog': {
            'text': 'You are going to delete all predictions from the selected tasks. Please confirm your action.',
            'type': 'confirm',
        },
    },
]
