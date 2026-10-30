"""Upload sliced tiles to a Label Studio project through the REST API.

Examples (PowerShell):
  $env:LABEL_STUDIO_TOKEN = "<your token>"

  # Create a new project with a rectangle-labels config and upload train + val tiles
  python upload_tiles.py --url http://ci-cdos-labelstudio-dev.ent.dfo-mpo.ca:8080 `
      --create-project "DIV2K tiles - train/val" --labels Car Person Ship `
      --tiles dataset/sliced/train dataset/sliced/val

  # Upload into an existing project
  python upload_tiles.py --url http://... --project-id 61 --tiles dataset/sliced/train
"""
import argparse
from pathlib import Path

from ls_auth import LabelStudio

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".tif": "image/tiff", ".tiff": "image/tiff"}


def labeling_config(labels):
    label_tags = "\n    ".join(f'<Label value="{l}"/>' for l in labels)
    # model_path / model_score_threshold are read by the YOLO ML backend
    return f"""<View>
  <Image name="image" value="$image" zoom="true" zoomControl="true"/>
  <RectangleLabels name="label" toName="image" model_path="best.pt" model_score_threshold="0.25">
    {label_tags}
  </RectangleLabels>
</View>"""


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", required=True, help="Label Studio base URL")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--project-id", type=int)
    g.add_argument("--create-project", metavar="TITLE", help="Create a new project with this title")
    p.add_argument("--labels", nargs="+", default=["Car", "Person", "Ship"],
                   help="Class names, in the SAME order as data.yaml (used with --create-project)")
    p.add_argument("--tiles", nargs="+", type=Path, required=True, help="Folder(s) of tile images")
    p.add_argument("--batch-size", type=int, default=50,
                   help="Files per request (Label Studio's default per-request limit is 100)")
    p.add_argument("--log", type=Path, default=Path("uploaded_tiles.txt"),
                   help="Records uploaded files so a rerun resumes instead of duplicating")
    args = p.parse_args()

    ls = LabelStudio(args.url)

    if args.create_project:
        r = ls.request("POST", "/api/projects/",
                       json={"title": args.create_project, "label_config": labeling_config(args.labels)})
        project_id = r.json()["id"]
        print(f"Created project {project_id}: {args.create_project}")
    else:
        project_id = args.project_id

    done = set(args.log.read_text(encoding="utf-8").split()) if args.log.exists() else set()

    files = []
    for folder in args.tiles:
        if not folder.is_dir():
            raise FileNotFoundError(folder)
        files += sorted(f for f in folder.iterdir() if f.suffix.lower() in IMAGE_EXTS)
    todo = [f for f in files if str(f.resolve()) not in done]
    print(f"{len(files)} tiles found, {len(files) - len(todo)} already uploaded, {len(todo)} to upload")

    with open(args.log, "a", encoding="utf-8") as log:
        for i in range(0, len(todo), args.batch_size):
            batch = todo[i:i + args.batch_size]
            ls.authenticate()  # PAT access tokens expire after ~5 min; refresh per batch
            handles = [open(f, "rb") for f in batch]
            try:
                payload = [("files", (f.name, h, MIME[f.suffix.lower()])) for f, h in zip(batch, handles)]
                r = ls.request("POST", f"/api/projects/{project_id}/import", files=payload)
            finally:
                for h in handles:
                    h.close()
            for f in batch:
                log.write(str(f.resolve()) + "\n")
            log.flush()
            print(f"  {min(i + args.batch_size, len(todo))}/{len(todo)} uploaded")

    # Confirm against the project's own count rather than the import response
    task_count = ls.request("GET", f"/api/projects/{project_id}/").json().get("task_number")
    print(f"Project {project_id} now has {task_count} tasks. Open {args.url}/projects/{project_id}/data")


if __name__ == "__main__":
    main()
