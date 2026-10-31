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

### Why stock Label Studio can only show a spinner

When you click **Retrieve Predictions > OK**, the page sends one request:

```
POST /api/dm/actions?id=retrieve_tasks_predictions&project=<ID>
body: { "selectedItems": { "all": true, "excluded": [] }, "filters": {...} }
```

The server works out which tasks are selected, sends all of them to the ML backend,
saves the boxes that come back, and only then answers. Until that single answer arrives,
the page has nothing to measure, so it shows a spinner. Large selections can also run
past the server's request timeout, which is why stock Label Studio's own dialog warned
about timeouts.

### What the patch changes

The work is split into many small requests, and the dialog updates after each one:

```
Browser (Data Manager)                         Label Studio server            ML backend
──────────────────────                         ───────────────────            ──────────
OK clicked
 │ 1. POST /api/dm/actions?id=selected_task_ids   ──►  resolve selection
 │    (same body as stock: select-all, filters)   ◄──  { task_ids: [2,3,…,36] }
 │    dialog opens: "0 of 35"
 │
 │ 2. POST /api/dm/actions?id=retrieve_tasks_predictions
 │    body: { selectedItems: { included: [2..11] } }  ──►  send 10 tasks  ──►  best.pt
 │                                                      save predictions ◄──  boxes
 │                                                 ◄──  { created: 10, with_predictions: 10 }
 │    bar → 10 of 35
 │ … repeat for [12..21], [22..31], [32..36], checking Stop before each …
 │
 └ 3. "Finished", Close → table and counts refresh
```

Three files change, all marked `[DFO progress patch]` in the source:

| File (in Label Studio) | Side | Change |
|---|---|---|
| `label_studio/data_manager/actions/basic.py` | Server (Python) | New hidden action `selected_task_ids`, which returns the selected task IDs. `retrieve_tasks_predictions` also returns `created` and `with_predictions` counts. |
| `web/libs/datamanager/src/stores/AppStore.js` | Web page (JavaScript) | `invokeAction()` sends Retrieve Predictions to the new `invokeActionInBatches()`, which runs steps 1-3 above. |
| `web/libs/datamanager/src/components/Common/ActionProgress/ActionProgress.jsx` | Web page (React) | The dialog: bar, times, counts, Stop and Close buttons. |

Details worth knowing:

- **Same selection as stock.** Step 1 uses the same request body as the stock action,
  so the server resolves "select all", filters and unticked rows with the same code
  (`ProjectActionsAPI.post`). The IDs it returns are exactly the tasks the stock action
  would have processed.
- **Same prediction code as stock.** Step 2 calls the unchanged action endpoint. Only
  the selection is smaller, so predictions are identical.
- **Hidden, but permission-checked.** `selected_task_ids` is registered with
  `'hidden': True`, which keeps it out of the Actions menu. It needs the same permission
  as Retrieve Predictions.
- **The counts.** Label Studio skips tasks that already have a prediction from the
  current model version. When the ML backend fails, it logs the error, saves nothing and
  still answers "Retrieved N predictions". The patched server counts afterwards:
  - `created`: predictions saved by this request
  - `with_predictions`: tasks that now have a prediction from this model version

  The dialog derives *skipped* = with_predictions − created, and *no prediction returned*
  = batch size − with_predictions.
- **Stop.** The loop checks a flag before sending each batch. A request already sent
  can't be recalled, so Stop takes effect after the current batch.
- **Errors.** A failed batch is counted as "no prediction returned" and its error is
  shown in the dialog. The run continues with the next batch instead of opening Label
  Studio's global error popup.
- **Batch size.** 10 tasks per request (`BATCHED_ACTIONS` in `AppStore.js`). That keeps
  each request short even with a slow model, and costs little extra overhead.

### How it gets into your installed Label Studio

Label Studio from pip contains Python source files and a web page that HumanSignal has
already compiled to JavaScript (`web/dist/apps/labelstudio/`). The server only hands
those compiled files to the browser and never rebuilds them. So:

- the Python change is a replacement `basic.py`
- the JavaScript changes were compiled once, here, from the patched source with
  Label Studio's own build (`yarn ls:build`), and the output folder ships as
  `labelstudio_frontend.zip`

`install_patch.py` copies `basic.py` over the installed one, replaces the
`web/dist/apps/labelstudio` folder with the zip's contents, and keeps the originals as
`.orig` backups for `--undo`. Neither Node.js nor a build is needed on your PC or the
server.

### Rebuilding from source

Needed only to change the patch, or to port it to another Label Studio version:

```bash
git clone --branch 1.23.2 --depth 1 https://github.com/HumanSignal/label-studio
cd label-studio
git am <path-to-repo>/label_studio_patch/retrieve-predictions-progress.patch
cd web
yarn install --frozen-lockfile
NODE_ENV=production yarn ls:build          # output: web/dist/apps/labelstudio
```

Then copy `label_studio/data_manager/actions/basic.py` to `basic.py` here, and zip
`web/dist/apps/labelstudio` (without the `.map` files) as `labelstudio_frontend.zip`.

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
