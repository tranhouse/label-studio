# Large Image Dataset into Label Studio

## Overview

Large aerial survey images are too big for Label Studio to render comfortably. This
project cuts them into 640 x 640 tiles with SAHI, annotates the tiles in Label Studio,
trains a YOLO model on them, and serves that model from a Label Studio ML backend so
new tiles are pre-annotated for review.

The model is a **mock model** used to build and test the workflow, not a production
detector.

Everything stays at tile level. Full-size images are never loaded into Label Studio.

## Workflow

| Step | What happens | Script |
|---|---|---|
| 1 | Collect raw images | - |
| 2 | Split images 70 / 15 / 15 into train, val and test | `split_dataset.py` |
| 3 | Slice every split into overlapping 640 px tiles (SAHI) | `slice_images.py` |
| 4 | Upload train + val tiles to a Label Studio project | `upload_tiles.py` |
| 5 | Annotate the tiles in Label Studio | Label Studio UI |
| 6 | Export annotations as a YOLO dataset (`data.yaml` + label files) | `export_to_yolo.py` |
| 7 | Train YOLO; validation each epoch selects `best.pt` | `train_yolo.py` |
| 8 | Serve `best.pt` from the ML backend | `yolo_ml_backend/` |
| 9 | Upload test tiles to a separate project, connect the backend, retrieve predictions, review | `upload_tiles.py` + Label Studio UI |

The ML backend hosts the model (`best.pt`) and runs inference. Label Studio connects
to it through the backend URL, sends it tasks, and displays the returned predictions
for review.

| Split | Share | Role |
|---|---|---|
| Train | 70% | Annotated; the model learns from it |
| Val | 15% | Annotated; scored each epoch to select `best.pt` (the model does not learn from it) |
| Test | 15% | Not annotated beforehand; pre-annotated by the backend and reviewed |

## Repository layout

```
split_dataset.py        Step 2  70/15/15 split (seed 42) -> dataset_splits/{train,val,test}.txt
slice_images.py         Step 3  SAHI tiles + tile_metadata.csv -> dataset/sliced/{train,val,test}/
upload_tiles.py         Steps 4, 9  Create project + labeling config, upload tiles via the REST API
export_to_yolo.py       Step 6  Label Studio annotations -> yolo_dataset/ (images, labels, data.yaml)
train_yolo.py           Step 7  YOLO training; prints the best.pt path, optionally copies it to the backend
ls_auth.py              Shared Label Studio authentication (Personal Access Token or legacy token)
yolo_ml_backend/        Step 8  Label Studio YOLO ML backend (see its README)
trained_model/          Earlier DIV2K model (Car / Person / Ship), kept for reference
experiments/            Early COCO128 experiments
```

## Setup (once)

```powershell
cd C:\Users\trant\label-studio
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install label-studio ultralytics sahi requests pillow
```

Start Label Studio in its own terminal and leave it running:

```powershell
label-studio start          # http://localhost:8080
```

Get a token from **Account & Settings** and set it in each terminal that runs the scripts:

```powershell
$env:LABEL_STUDIO_TOKEN = 'paste-token-here'
```

## Run the pipeline

Keep raw images under `data\` (git-ignored). Replace `<ID>` with the project number
shown in the browser address bar (`/projects/<ID>/`).

```powershell
# 2. Split
python split_dataset.py --input data\pilot --output dataset_splits

# 3. Slice (train, val and test)
python slice_images.py --splits dataset_splits --output dataset/sliced

# 4. Upload train + val tiles (creates the project and labeling config)
python upload_tiles.py --url http://localhost:8080 --create-project "Tiles - train/val" `
    --labels Ship Vehicle --tiles dataset/sliced/train dataset/sliced/val

# 5. Annotate in Label Studio. Submit tiles with no objects as empty (background).

# 6. Export to YOLO format
python export_to_yolo.py --url http://localhost:8080 --project-id <ID> `
    --train-dir dataset/sliced/train --val-dir dataset/sliced/val --classes Ship Vehicle

# 7. Train and copy best.pt into the backend
python train_yolo.py --data yolo_dataset/data.yaml --epochs 50 --copy-to-backend

# 8. Start the ML backend: see yolo_ml_backend/README.md

# 9. Upload test tiles to their own project
python upload_tiles.py --url http://localhost:8080 --create-project "Tiles - test" `
    --labels Ship Vehicle --tiles dataset/sliced/test
```

Then in the test project:

1. **Settings > Model > Connect Model**, Backend URL `http://localhost:9090`, **Validate and Save**.
2. In the Data Manager, select all tasks, then **Actions > Retrieve Predictions**.
3. Open each tile, correct or delete the predicted boxes, and submit.

Avoid **Create Annotations from Predictions** on the test set: it saves unreviewed
predictions as annotations.

## Keep class names consistent

The labels in the Label Studio project, `--labels`, `--classes`, and the class names
inside `best.pt` must match exactly, in the same order. The backend matches model
classes to Label Studio labels by name and silently drops anything that does not match.

## How annotations become a YOLO dataset

`export_to_yolo.py` pulls the project export through the API, maps each task back to
the local tile (Label Studio prefixes uploaded file names with a hash), and uses the
tile's folder to assign train or val. Label Studio stores boxes as top-left x/y and
width/height in percent; YOLO needs normalized centre x/y and width/height:

```
cx = (x + width/2) / 100    cy = (y + height/2) / 100    w = width/100    h = height/100
```

Each tile gets `labels/<split>/<tile>.txt` with lines `<class_id> cx cy w h`. Empty files
mark background tiles. `data.yaml` lists the dataset path, train/val folders and class
names. Rotated boxes are exported axis-aligned (with a warning), so add
`canRotate="false"` to `RectangleLabels` in the labeling config.

## Notes

- Tiles that cross object boundaries: box the visible part. With 20% overlap most
  objects appear whole in at least one tile.
- Moving to the DFO Label Studio server: the server must be able to reach the backend
  URL over the network. `localhost` only works when both run on the same machine.
- Never commit tokens, `.env` files, or imagery. `.gitignore` covers the data folders.
