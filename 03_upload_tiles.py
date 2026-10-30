"""Steps 3 and 8: upload sliced tiles to a Label Studio project through the REST API.

Used twice in the workflow:
  * Step 3: upload train + val tiles to a project for annotation.
  * Step 8: upload test tiles to a separate project for ML backend predictions.

With --create-project, the script also creates the project and its labeling config
(rectangle boxes with the given labels, set up for the YOLO ML backend).

Uploaded files are recorded in uploaded_tiles.txt, so if an upload is interrupted,
rerunning the same command skips the tiles already sent instead of duplicating them.

Examples (PowerShell):
    $env:LABEL_STUDIO_TOKEN = 'paste-token-here'

    # Create a project and upload train + val tiles
    python 03_upload_tiles.py --url http://localhost:8080 --create-project "Pilot - train/val" `
        --labels Ship Vehicle --tiles dataset/sliced/train dataset/sliced/val

    # Upload into an existing project (ID from the browser address bar)
    python 03_upload_tiles.py --url http://localhost:8080 --project-id 1 --tiles dataset/sliced/train
"""
import argparse
from pathlib import Path

from ls_auth import LabelStudio

# File types uploaded as tiles, and the content type sent with each
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".tif": "image/tiff", ".tiff": "image/tiff"}


def parse_args():
    """Read the command-line options.

    Exactly one of --project-id or --create-project must be given.

    Returns:
        argparse.Namespace with url, project_id or create_project, labels, tiles,
        batch_size and log.
    """
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", required=True, help="Label Studio base URL, e.g. http://localhost:8080")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--project-id", type=int, help="Upload into this existing project")
    g.add_argument("--create-project", metavar="TITLE", help="Create a new project with this title")
    p.add_argument("--labels", nargs="+", default=["Ship", "Vehicle"],
                   help="Class names, in the SAME order as --classes in 05_export_to_yolo.py "
                        "(used with --create-project)")
    p.add_argument("--tiles", nargs="+", type=Path, required=True, help="Folder(s) of tile images")
    p.add_argument("--batch-size", type=int, default=50,
                   help="Files per request (Label Studio's default per-request limit is 100)")
    p.add_argument("--log", type=Path, default=Path("uploaded_tiles.txt"),
                   help="Records uploaded files so a rerun resumes instead of duplicating")
    return p.parse_args()


def labeling_config(labels):
    """Build the Label Studio labeling config (XML) for drawing boxes on tiles.

    Args:
        labels: Class names, e.g. ["Ship", "Vehicle"].

    Returns:
        The labeling config as an XML string. Its attributes mean:
            zoom / zoomControl     annotators can zoom into a tile
            model_path="best.pt"   which file in yolo_ml_backend/models/ the backend loads
            model_score_threshold  the backend drops predictions below this confidence
            canRotate="false"      boxes can't be rotated (YOLO only supports straight boxes)
    """
    label_tags = "\n    ".join(f'<Label value="{label}"/>' for label in labels)
    return f"""<View>
  <Image name="image" value="$image" zoom="true" zoomControl="true"/>
  <RectangleLabels name="label" toName="image" model_path="best.pt" model_score_threshold="0.25" canRotate="false">
    {label_tags}
  </RectangleLabels>
</View>"""


def get_project_id(ls, args):
    """Return the project to upload into, creating it first if --create-project was given.

    Args:
        ls: Authenticated LabelStudio client.
        args: Parsed command-line options.

    Returns:
        The project ID (int).
    """
    if not args.create_project:
        return args.project_id

    r = ls.request("POST", "/api/projects/",
                   json={"title": args.create_project, "label_config": labeling_config(args.labels)})
    project_id = r.json()["id"]
    print(f"Created project {project_id}: {args.create_project}")
    return project_id


def collect_tiles(folders):
    """List the tile images in one or more folders.

    Args:
        folders: Folders to read, e.g. [dataset/sliced/train, dataset/sliced/val].

    Returns:
        A list of image paths, sorted by name within each folder. Non-image files such
        as tile_metadata.csv are ignored.

    Raises:
        FileNotFoundError: If a folder doesn't exist.
    """
    files = []
    for folder in folders:
        if not folder.is_dir():
            raise FileNotFoundError(folder)
        files += sorted(f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTS)
    return files


def load_upload_log(log_path):
    """Read the set of tiles already uploaded by earlier runs.

    Args:
        log_path: The log file (uploaded_tiles.txt). It may not exist yet.

    Returns:
        A set of absolute file paths, as strings.
    """
    if not log_path.exists():
        return set()
    return set(log_path.read_text(encoding="utf-8").splitlines())


def upload_batch(ls, project_id, batch):
    """Upload one batch of tiles; each file becomes one task in the project.

    Args:
        ls: Authenticated LabelStudio client.
        project_id: Project to import into.
        batch: List of tile paths.
    """
    # Refresh the token first: a Personal Access Token's access token expires after a few
    # minutes, and an upload can't be retried automatically once its files have been read
    ls.authenticate()

    handles = [open(f, "rb") for f in batch]
    try:
        # Multipart upload: one ("files", (name, file, content type)) entry per tile
        payload = [("files", (f.name, h, MIME[f.suffix.lower()])) for f, h in zip(batch, handles)]
        ls.request("POST", f"/api/projects/{project_id}/import", files=payload)
    finally:
        # Always close the files, even if the upload failed
        for h in handles:
            h.close()


def main():
    """Create or pick the project, upload any tiles not yet sent, and confirm the task count."""
    args = parse_args()
    ls = LabelStudio(args.url)
    project_id = get_project_id(ls, args)

    # Skip tiles recorded in the log by a previous (possibly interrupted) run
    files = collect_tiles(args.tiles)
    done = load_upload_log(args.log)
    todo = [f for f in files if str(f.resolve()) not in done]
    print(f"{len(files)} tiles found, {len(files) - len(todo)} already uploaded, {len(todo)} to upload")

    with open(args.log, "a", encoding="utf-8") as log:
        for i in range(0, len(todo), args.batch_size):
            batch = todo[i:i + args.batch_size]
            upload_batch(ls, project_id, batch)

            # Record the batch only after it uploaded successfully, and save the log
            # straight away so a crash on the next batch doesn't lose it
            for f in batch:
                log.write(str(f.resolve()) + "\n")
            log.flush()
            print(f"  {min(i + args.batch_size, len(todo))}/{len(todo)} uploaded")

    # Confirm against the project's own count rather than the import response
    task_count = ls.request("GET", f"/api/projects/{project_id}/").json().get("task_number")
    print(f"Project {project_id} now has {task_count} tasks. Open {args.url}/projects/{project_id}/data")


if __name__ == "__main__":
    main()
