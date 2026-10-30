# Large Image Dataset into Label Studio

## Overview

Large aerial survey images are too big for Label Studio to render comfortably. This
project cuts them into 640 x 640 tiles with SAHI, annotates the tiles in Label Studio,
trains a YOLO model on them, and serves that model from a Label Studio ML backend so
new tiles are pre-annotated for review.

The model is a **mock model** used to build and test the workflow, not a production
detector. Everything stays at tile level: full-size images are never loaded into
Label Studio.

The ML backend hosts the model (`best.pt`) and runs inference. Label Studio connects
to it through the backend URL, sends it tasks, and displays the returned predictions
for review.

```
Raw images -> split 70/15/15 -> SAHI slicing (640 px tiles) -> annotate train/val tiles in Label Studio
    -> export to YOLO format -> train YOLO (val selects best.pt) -> ML backend serves best.pt
    -> test tiles in Label Studio get predictions from the backend -> human review
```

| Split | Share | Role |
|---|---|---|
| Train | 70% | Annotated; the model learns from it |
| Val | 15% | Annotated; scored after every epoch to select `best.pt` (the model does not learn from it) |
| Test | 15% | Not annotated beforehand; pre-annotated by the backend, then reviewed |

## Repository layout

| Path | Step | Purpose |
|---|---|---|
| `02a_split_dataset.py` | 2 | 70/15/15 split (seed 42) into `dataset_splits/{train,val,test}.txt` |
| `02b_slice_images.py` | 2 | SAHI tiles plus `tile_metadata.csv` in `dataset/sliced/{train,val,test}/` |
| `03_upload_tiles.py` | 3, 8 | Creates a project and labeling config, uploads tiles through the REST API |
| `05_export_to_yolo.py` | 5 | Converts Label Studio annotations to `yolo_dataset/` (images, labels, `data.yaml`) |
| `06_train_yolo.py` | 6 | Trains YOLO, prints the `best.pt` path, can copy it into the backend |
| `ls_auth.py` | - | Shared Label Studio authentication (Personal Access Token or legacy token) |
| `yolo_ml_backend/` | 7 | Label Studio YOLO ML backend |
| `trained_model/` | - | Earlier DIV2K model (Car / Person / Ship), kept for reference |
| `experiments/` | - | Early COCO128 experiments |

---

## Before you start

**Placeholders.** Anything in angle brackets, such as `<ID>`, is a placeholder. Replace
the whole thing, brackets included, with the real value. PowerShell rejects a literal `<`.

`<path-to-repo>` is the folder you cloned this repository into, for example
`C:\Users\<username>\label-studio`. Commands after a `cd <path-to-repo>` use paths
relative to that folder, so run them from there.

**Quotes.** Put tokens in single quotes: `'abc123'`.

**Environment variables.** `$env:NAME = '...'` only lasts for that PowerShell window.
Set it again in every new window.

**Terminals.** You will use three PowerShell windows:

| Window | Runs | Leave it open? |
|---|---|---|
| 1 | Label Studio (`label-studio start`) | Yes |
| 2 | The pipeline scripts | - |
| 3 | The ML backend (step 7) | Yes |

---

## Setup (once)

### Python environment (window 2)

```powershell
cd <path-to-repo>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install label-studio ultralytics sahi requests pillow
```

The prompt starts with `(.venv)` when the environment is active. If a script fails with
`ModuleNotFoundError`, the environment isn't active in that window. Activate it and rerun.

### Start Label Studio (window 1)

```powershell
cd <path-to-repo>
.\.venv\Scripts\Activate.ps1
label-studio start
```

It opens at `http://localhost:8080`. Sign up; the account is local to your PC.

### Get your token

The scripts and the backend authenticate with a token from Label Studio.

1. Go to **Organization > API Tokens Settings** and make sure **Legacy tokens** are enabled.
2. Go to your avatar (top right) > **Account & Settings** and copy the **Legacy Token**.
   It is a short string of letters and numbers.
3. In window 2:

```powershell
$env:LABEL_STUDIO_TOKEN = 'paste-token-here'
$env:LABEL_STUDIO_TOKEN     # prints the token back to confirm
```

The scripts also accept a Personal Access Token (a long string containing dots), but
use the legacy token for the ML backend in step 7.

---

## Step 1: Collect raw images

The pilot uses 10 aerial images from the DOTA dataset. These are large images with small
ships and vehicles, which is close to aerial survey imagery. Raw images go in `data\`,
which is git-ignored.

```powershell
cd <path-to-repo>
mkdir data -Force
curl.exe -L -o data\DOTAv1.zip https://github.com/ultralytics/assets/releases/download/v0.0.0/DOTAv1.zip
Expand-Archive data\DOTAv1.zip -DestinationPath data

mkdir data\pilot -Force
Get-ChildItem data\DOTAv1\images\train\* | Get-Random -Count 10 -SetSeed 42 |
    Copy-Item -Destination data\pilot
```

For a full run, change `-Count 10` to 50-100 and use a new folder name.

## Step 2: Split and slice

```powershell
# 70 / 15 / 15 split
python 02a_split_dataset.py --input data\pilot --output dataset_splits

# Slice train, val and test into 640 px tiles with 20% overlap (SAHI)
python 02b_slice_images.py --splits dataset_splits --output dataset/sliced
```

All three splits are sliced. Train and val tiles are annotated; test tiles are used in
step 8. Each split folder also gets `tile_metadata.csv`, which records each tile's
position in its original image.

## Step 3: Upload train + val tiles to Label Studio

```powershell
python 03_upload_tiles.py --url http://localhost:8080 --create-project "Pilot - train/val" `
    --labels Ship Vehicle --tiles dataset/sliced/train dataset/sliced/val
```

This creates the project with a rectangle-labelling config for **Ship** and **Vehicle**,
uploads the tiles in batches, and prints the project ID (`Created project 1: ...`).
If an upload is interrupted, rerun the same command. Tiles already uploaded are
skipped.

The project ID is also the number after `/projects/` in the browser address bar:
`http://localhost:8080/projects/1/data`.

Before annotating, stop boxes from being rotated (YOLO only supports straight boxes):
**Settings > Labeling Interface > Code**, then add `canRotate="false"` to the
`RectangleLabels` line and save:

```xml
<RectangleLabels name="label" toName="image" model_path="best.pt" model_score_threshold="0.25" canRotate="false">
```

## Step 4: Annotate in Label Studio

| Class | Box these | Ignore |
|---|---|---|
| **Ship** | Any watercraft: boats, ships, yachts, ferries | Planes, buildings, storage tanks, harbours, people |
| **Vehicle** | Any road vehicle: cars, trucks, buses, vans | |

- Draw boxes tight around the visible object.
- An object cut off at a tile edge: box the visible part. With 20% overlap, most objects
  appear whole in at least one tile.
- A tile with nothing to label: click **Submit** with no boxes. These become background
  examples for training.
- Skip objects too small or unclear to identify, and be consistent about it.
- Only submitted tiles are exported.

## Step 5: Export annotations as a YOLO dataset

Replace `<ID>` with the train/val project ID from step 3:

```powershell
python 05_export_to_yolo.py --url http://localhost:8080 --project-id <ID> `
    --train-dir dataset/sliced/train --val-dir dataset/sliced/val --classes Ship Vehicle
```

Output:

```
yolo_dataset/
  images/train/   images/val/     tile images
  labels/train/   labels/val/     one .txt per tile: <class_id> cx cy w h
  data.yaml                       dataset path, train/val folders, class names
```

How the boxes are converted: Label Studio stores the top-left x/y and width/height as
percentages of the tile. YOLO needs the normalized centre and size:

```
cx = (x + width/2) / 100    cy = (y + height/2) / 100    w = width / 100    h = height / 100
```

The summary at the end shows train tiles, val tiles, boxes and anything skipped. Check
that train and val are not 0. A `rotated box ... exported as axis-aligned` warning means
a box was rotated; redraw it without rotation and export again.

## Step 6: Train YOLO

```powershell
python 06_train_yolo.py --data yolo_dataset/data.yaml --epochs 10 --copy-to-backend
```

- Every epoch, YOLO learns from the train tiles, then scores the val tiles. The epoch with
  the best validation mAP is saved as `best.pt`.
- The final lines print where `best.pt` is saved (for example
  `runs\detect\tiles\weights\best.pt`). `--copy-to-backend` copies it to
  `yolo_ml_backend\models\best.pt`.
- Use `--device 0` if you have an NVIDIA GPU. For a full run, use `--epochs 50`.
- With only a handful of pilot tiles, scores will be near zero. That is expected; the
  pilot only needs a valid `best.pt`.

## Step 7: Start the ML backend (window 3)

The backend runs directly with Python, so Docker is not needed. It uses its own virtual
environment because it installs development versions of the Label Studio SDK.

**First time only:**

```powershell
cd <path-to-repo>\yolo_ml_backend
python -m venv .venv-backend
.\.venv-backend\Scripts\Activate.ps1
python -m pip install -r requirements-base.txt -r requirements.txt
```

**Every time:**

```powershell
cd <path-to-repo>\yolo_ml_backend
.\.venv-backend\Scripts\Activate.ps1
$env:LABEL_STUDIO_URL = 'http://localhost:8080'
$env:LABEL_STUDIO_HOST = 'http://localhost:8080'
$env:LABEL_STUDIO_API_KEY = 'paste-legacy-token-here'
python _wsgi.py --port 9090
```

Leave this window open. Check `http://localhost:9090/health` in a browser; it should
show `"status": "UP"`.

The backend loads `models\best.pt` because the labeling config contains
`model_path="best.pt"`. After replacing `best.pt`, stop the backend (Ctrl+C) and start it
again. `yolo_ml_backend/README.md` covers the Docker option.

## Step 8: Predictions on the test tiles

Upload the test tiles to a **separate** project so they don't mix with the annotated
training data (window 2):

```powershell
cd <path-to-repo>
python 03_upload_tiles.py --url http://localhost:8080 --create-project "Pilot - test" `
    --labels Ship Vehicle --tiles dataset/sliced/test
```

The last line confirms how many tasks the project has. It should equal the number of test tiles.

Then in Label Studio, in the test project:

1. **Settings > Model > Connect Model.** Enter a name (for example `YOLO pilot`) and the
   backend URL `http://localhost:9090`, then click **Validate and Save**.
2. In the Data Manager, tick the box at the top to select all tasks, then choose
   **Actions > Retrieve Predictions**.
3. Open each tile. Predicted boxes appear as pre-annotations. Correct or delete the wrong
   ones, add any missed, and submit.

Optional: to have predictions appear automatically when a tile is opened, turn on
**Settings > Annotation > Use predictions to prelabel tasks** and select the model.

**Do not use Create Annotations from Predictions on the test set.** It saves every
prediction as an annotation without review, including wrong boxes.

**The pilot is complete when predicted boxes appear on the test tiles.** A pilot model
is rarely confident enough to pass the 0.25 threshold. To confirm the connection works,
temporarily set `model_score_threshold="0.01"` in **Settings > Labeling Interface > Code**,
save, and retrieve predictions again.

---

## After the pilot

| Phase | What changes |
|---|---|
| **Full run** | Repeat steps 1-8 with 50-100 images and about 50 epochs |
| **DFO server** | Run the backend somewhere the DFO Label Studio server can reach (an Azure VM or container on the DFO network, or a Linux workstation). Set `LABEL_STUDIO_URL` and `LABEL_STUDIO_HOST` to `http://ci-cdos-labelstudio-dev.ent.dfo-mpo.ca:8080`, get a token from that server, and use that URL with `--url` |

On the DFO server, `http://localhost:9090` will not work as the backend URL: Label Studio
sends requests from the server, so the backend must be reachable from there.

## Keep class names consistent

These must match exactly, in the same order:

1. The labels in the Label Studio project (`--labels` in `03_upload_tiles.py`)
2. `--classes` in `05_export_to_yolo.py`
3. The class names in `best.pt` (set automatically from `data.yaml`)

The backend matches model classes to Label Studio labels by name and silently drops
anything that doesn't match.

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Activate the right environment (`.venv` for scripts, `.venv-backend` for the backend) or run `python -m pip install <package>` |
| `The '<' operator is reserved for future use` | Replace the `<placeholder>` with the real value, without brackets |
| `Cannot find path ... best.pt` | `best.pt` is inside the run's `weights` folder; use the path printed at the end of training |
| `docker` is not recognized | Docker isn't installed; use the Python option in step 7 |
| pip conflict on `numpy<2` while installing the backend | `yolo_ml_backend/requirements.txt` must contain `numpy>=2.2` (already fixed in this repo) |
| Validate and Save fails | Check the backend window is running and `http://localhost:9090/health` returns `UP` |
| 401 / 403 errors in the backend window | The backend can't download tiles; set `LABEL_STUDIO_API_KEY` to the legacy token and restart it |
| Retrieve Predictions returns no boxes | Lower `model_score_threshold`, and check that the label names match the model's classes |

## Security

Never commit tokens, `.env` files or imagery. `.gitignore` covers `data/`, `dataset/`,
`dataset_splits/`, `yolo_dataset/`, `runs/` and both virtual environments.
