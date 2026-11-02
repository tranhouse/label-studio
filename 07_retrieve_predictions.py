"""Step 8: get predictions from the ML backend for a project, with a progress bar.

This does the same thing as selecting tasks in the Data Manager and choosing
Actions > Retrieve Predictions: Label Studio sends each tile to the connected ML backend,
which runs best.pt and returns bounding boxes, saved as predictions (pre-annotations
for review). The difference is that the button sends every selected task in one request
and shows only a spinner, while this script sends them a few at a time and shows how
many are done, how fast it's going, and how long is left.

It calls Label Studio's own Retrieve Predictions action, so the results are identical
to the button's: same backend, same model, same score threshold from the labeling config.

Label Studio skips tasks that already have a prediction from the current model version,
so if a run is interrupted, rerun the same command: finished tiles go by quickly and it
carries on from where it stopped. After replacing best.pt and restarting the backend,
the model version changes and every tile is predicted again.

Requirements: the ML backend is running and connected to the project
(Settings > Model > Connect Model). tqdm is installed with ultralytics and sahi.

Example (PowerShell):
    $env:LABEL_STUDIO_TOKEN = 'paste-token-here'
    python 07_retrieve_predictions.py --url http://localhost:8080 --project-id 2
"""
import argparse
import time

from tqdm import tqdm

from ls_auth import LabelStudio


def parse_args():
    """Read the command-line options.

    Returns:
        argparse.Namespace with url, project_id, batch_size and only_missing.
    """
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", required=True, help="Label Studio base URL, e.g. http://localhost:8080")
    p.add_argument("--project-id", type=int, required=True,
                   help="Project whose tasks get predictions (ID from the browser address bar)")
    p.add_argument("--batch-size", type=int, default=10,
                   help="Tiles sent per request. Smaller updates the bar more often; larger is "
                        "slightly faster overall. Each request must finish within 5 minutes.")
    p.add_argument("--only-missing", action="store_true",
                   help="Skip tiles that already have any prediction, even from an older model")
    return p.parse_args()


def check_backend(ls, project_id):
    """Make sure an ML backend is connected to the project before starting.

    Args:
        ls: Authenticated LabelStudio client.
        project_id: Project to check.

    Returns:
        The connected backend's title and URL, for the start-up message.

    Raises:
        SystemExit: If no backend is connected.
    """
    backends = ls.request("GET", "/api/ml/", params={"project": project_id}).json()
    if not backends:
        raise SystemExit(f"No ML backend is connected to project {project_id}. In Label Studio, open "
                         "the project's Settings > Model > Connect Model and enter the backend URL "
                         "(e.g. http://localhost:9090), then rerun.")
    backend = backends[0]
    return f"{backend.get('title') or 'ML backend'} ({backend.get('url')})"


def list_tasks(ls, project_id):
    """List every task in the project with its prediction count.

    Args:
        ls: Authenticated LabelStudio client.
        project_id: Project to read.

    Returns:
        A list of (task_id, total_predictions) tuples, in task order.
    """
    tasks, page, page_size = [], 1, 100
    while True:
        data = ls.request("GET", "/api/tasks/",
                          params={"project": project_id, "page": page, "page_size": page_size}).json()
        batch = data.get("tasks", [])
        tasks += [(t["id"], t.get("total_predictions", 0)) for t in batch]
        # Stop on a short page, or once the total Label Studio reports has been read
        if len(batch) < page_size or len(tasks) >= data.get("total", 0):
            return tasks
        page += 1


def retrieve_batch(ls, project_id, task_ids):
    """Run Label Studio's Retrieve Predictions action on a batch of tasks.

    This is the same request the Data Manager sends when you select these tasks and
    choose Actions > Retrieve Predictions. Label Studio forwards the tiles to the ML
    backend and saves what it returns. It waits until the batch is finished.

    Args:
        ls: Authenticated LabelStudio client.
        project_id: Project the tasks belong to.
        task_ids: IDs of the tasks in this batch.
    """
    # /api/dm/actions runs a Data Manager action; "id" names the action and
    # selectedItems with all=False + included=[...] limits it to exactly these tasks
    ls.request("POST", "/api/dm/actions",
               params={"id": "retrieve_tasks_predictions", "project": project_id},
               json={"selectedItems": {"all": False, "included": task_ids}})


def main():
    """Check the backend, then predict the project's tasks batch by batch with a progress bar."""
    args = parse_args()
    ls = LabelStudio(args.url)

    # Fail early with clear instructions if no model is connected to the project
    backend = check_backend(ls, args.project_id)

    # Every task in the project; with --only-missing, just the ones with no prediction yet
    tasks = list_tasks(ls, args.project_id)
    if args.only_missing:
        todo = [task_id for task_id, n in tasks if n == 0]
    else:
        todo = [task_id for task_id, _ in tasks]

    print(f"Project {args.project_id}: {len(tasks)} tasks, {len(todo)} to send to {backend}")
    if not todo:
        print("Nothing to do.")
        return

    start = time.time()
    # tqdm draws the progress bar in the terminal and works out the speed and time left
    # from how fast bar.update() is called
    with tqdm(total=len(todo), unit="tile", desc="Predicting") as bar:
        # One request per batch: each returns once the backend has predicted those tiles,
        # which is what lets the bar move as the run progresses
        for i in range(0, len(todo), args.batch_size):
            batch = todo[i:i + args.batch_size]
            try:
                retrieve_batch(ls, args.project_id, batch)
            except RuntimeError as e:
                # Keep going so one bad batch doesn't stop the run; report it at the end
                # (tqdm.write prints above the bar without breaking it)
                tqdm.write(f"  Batch starting at task {batch[0]} failed: {e}")
            # Advance the bar by this batch whether it succeeded or not
            bar.update(len(batch))

    # Check against Label Studio rather than trusting the action's reply: if the backend
    # errors, Label Studio logs it and still answers 200 without saving predictions
    counts = dict(list_tasks(ls, args.project_id))
    missing = [task_id for task_id in todo if counts.get(task_id, 0) == 0]
    minutes = (time.time() - start) / 60

    print(f"Done in {minutes:.1f} min. {len(todo) - len(missing)}/{len(todo)} tiles now have predictions.")
    if missing:
        print(f"{len(missing)} tiles have no prediction (first IDs: {missing[:10]}). Check the backend "
              "window for errors, then rerun this command to retry them.")
    print(f"Review them at {args.url}/projects/{args.project_id}/data")


if __name__ == "__main__":
    main()
