# Label Studio patch: progress bar for Retrieve Predictions

A change to **Label Studio 1.23.2 itself**, not to this pipeline. After installing it,
**Data Manager > select tiles > Actions > Retrieve Predictions** opens a progress dialog
instead of a spinner:

- a bar that fills as the tiles are sent to the ML backend 10 at a time, with elapsed
  time and time left
- three counts: **New predictions**, **Already predicted (skipped)** and **No prediction
  returned**. Stock Label Studio says "Retrieved N predictions" even when the backend is
  down; this tells you how many tiles actually got boxes
- a **Stop** button that finishes the current batch and stops. Running Retrieve
  Predictions again carries on, because tiles that already have predictions from the
  current model are skipped

Sending 10 tiles per request also avoids the timeout that stock Label Studio warns about
for large selections.

Nothing else changes: the same ML backend, `best.pt` and score threshold are used, and
the predictions are identical to stock Label Studio's.

## Install on your PC

Use the same PowerShell window and `.venv` that you run `label-studio start` from.

1. Stop Label Studio (Ctrl+C in its window).
2. Get the latest code and install the patch:

   ```powershell
   cd <path-to-repo>
   git pull
   .\.venv\Scripts\Activate.ps1
   python label_studio_patch/install_patch.py
   ```

   It checks that Label Studio 1.23.2 is installed (`python -m pip install
   label-studio==1.23.2` if not) and keeps the stock files as backups.
3. Start Label Studio again (`label-studio start`) and refresh the browser with **Ctrl+F5**
   so it loads the new page code.

To go back to stock Label Studio: stop it, run
`python label_studio_patch/install_patch.py --undo`, and start it again.

Reinstalling or upgrading Label Studio with pip replaces the patched files, so run
`install_patch.py` again afterwards (it only supports 1.23.2).

## Use it

1. Connect the model to the project as usual (Settings > Model > Connect Model).
2. In the Data Manager, select the tiles (tick the top box for all), then
   **Actions > Retrieve Predictions > OK**.
3. Watch the dialog; click **Close** when it finishes. The table refreshes with the
   prediction counts.

If **No prediction returned** is above 0, those tiles got no boxes above the score
threshold or the backend had an error (check the backend window). Fix the cause and run
Retrieve Predictions again on the same selection.

## DFO server

The DFO Label Studio server (`ci-cdos-labelstudio-dev`) runs stock Label Studio, so this
only appears there once whoever maintains the server applies the same two files. They
can run `install_patch.py` in the server's Python environment, or build a Docker image
with it applied. It touches no database tables and adds no settings, and `--undo` reverts
it.

## Files

| File | Purpose |
|---|---|
| `install_patch.py` | Installs or removes the patch in the active Python environment |
| `basic.py` | Patched `label_studio/data_manager/actions/basic.py` (server side) |
| `labelstudio_frontend.zip` | Patched build of `web/dist/apps/labelstudio` (the web page) |
| `retrieve-predictions-progress.patch` | Source diff against the `1.23.2` tag of [HumanSignal/label-studio](https://github.com/HumanSignal/label-studio), for review or rebuilding |

## How it works

- **Server** (`basic.py`): a hidden action, `selected_task_ids`, returns the IDs of the
  selected tasks. It resolves "select all", filters and exclusions exactly as the normal
  action does. `retrieve_tasks_predictions` now also returns `created` and
  `with_predictions` counts. Its existing response fields are unchanged.
- **Web page** (`ActionProgress.jsx`, `AppStore.js` in the Data Manager): Retrieve
  Predictions asks for the IDs, then calls the normal action for 10 tasks at a time and
  updates the dialog after each call.

To rebuild from source: check out tag `1.23.2` of HumanSignal/label-studio, `git am`
the `.patch`, then in `web/` run `yarn install --frozen-lockfile` and
`NODE_ENV=production yarn ls:build`. The result is in `web/dist/apps/labelstudio`.

## Tested

On Label Studio 1.23.2 with 35 tiles and a stand-in ML backend, in a real browser:

- All 35 tiles: the bar advanced 10 at a time; 35 new predictions, and the table showed
  35 predictions afterwards
- Stop pressed mid-run: stopped at 20 of 35; running again gave 15 new and 20 skipped
- ML backend down: 35 tiles with no prediction returned, with the explanation shown
  (stock Label Studio reports success in this case)
- `install_patch.py`: install, reinstall, and `--undo` restore the stock files byte for
  byte

Not yet tested with the real YOLO backend and `best.pt`.
