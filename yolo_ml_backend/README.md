# YOLO ML Backend

This is the Label Studio YOLO ML backend (from HumanSignal's `label-studio-ml-backend`).
It hosts the trained model and returns bounding-box predictions to Label Studio.

## How it finds the model

The project's labeling config names the model file, and the backend loads it from `models/`:

```xml
<RectangleLabels name="label" toName="image" model_path="best.pt" model_score_threshold="0.25" canRotate="false">
```

Put the trained weights at `yolo_ml_backend/models/best.pt`
(`python 06_train_yolo.py --copy-to-backend` does this). Restart the backend after replacing the file.

## Token

The backend downloads each tile from Label Studio, so it needs a token. Use a
**legacy token**: enable it under **Organization > API Tokens Settings**, then copy it from
**Account & Settings**.

## Option A: run with Python (Windows, no Docker)

Use a separate virtual environment, because this installs development versions of
the Label Studio SDK.

```powershell
cd <path-to-repo>\yolo_ml_backend
python -m venv .venv-backend
.\.venv-backend\Scripts\Activate.ps1
python -m pip install -r requirements-base.txt -r requirements.txt

$env:LABEL_STUDIO_URL = 'http://localhost:8080'
$env:LABEL_STUDIO_HOST = 'http://localhost:8080'
$env:LABEL_STUDIO_API_KEY = 'paste-legacy-token-here'
python _wsgi.py --port 9090
```

Check it at `http://localhost:9090/health` (should return `"status": "UP"`).

## Option B: run with Docker

```powershell
cd yolo_ml_backend
$env:LABEL_STUDIO_API_KEY = 'paste-legacy-token-here'
docker compose up --build
```

Inside Docker, `localhost` is the container itself, so `docker-compose.yml` reaches a
Label Studio on the same computer through `http://host.docker.internal:8080`.

## Connect Label Studio

1. In the project, open **Settings > Model > Connect Model**.
2. Backend URL: `http://localhost:9090`, then **Validate and Save**.
3. In the Data Manager, select tasks, then **Actions > Retrieve Predictions**.

To have predictions appear automatically when a task is opened, turn on
**Settings > Annotation > Use predictions to prelabel tasks** and select the model.

## Troubleshooting

- **No boxes returned:** the model may not be confident enough. Temporarily lower
  `model_score_threshold` (for example to `0.01`) to confirm the connection works.
- **401 / 403 when fetching images:** wrong token type or value. Use the legacy token.
- **Labels missing:** the model's class names must exactly match the label values in the labeling config.
- **pip conflict on numpy:** `requirements.txt` must allow `numpy>=2.2` for the current SDK.

Do not commit `.env` files, tokens or passwords.
