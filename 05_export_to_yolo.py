"""Step 5: export annotations from Label Studio and build a YOLO dataset from your local tiles.

What it does:
  1. Downloads the project's annotations (or reads a JSON export with --from-file).
  2. Matches each Label Studio task to the tile on your disk. Label Studio adds a
     hash prefix to uploaded files ("0793_x0_y0.png" -> "a1b2c3d4-0793_x0_y0.png"),
     so the prefix is removed before matching.
  3. Uses the folder the tile is in (--train-dir or --val-dir) to decide its split.
  4. Converts each box to YOLO format and writes one label file per tile.
  5. Writes data.yaml for training.

Tiles submitted with no boxes become background images (an empty label file), which
helps the model learn what "nothing here" looks like. Tasks nobody has submitted are
skipped.

Output:
    yolo_dataset/
      images/train/  images/val/    copies of the annotated tiles
      labels/train/  labels/val/    one .txt per tile: <class_id> cx cy w h
      data.yaml                     dataset path, folders and class names
      labelstudio_export.json       raw export, kept for reference

Example (PowerShell):
    python 05_export_to_yolo.py --url http://localhost:8080 --project-id 1 `
        --train-dir dataset/sliced/train --val-dir dataset/sliced/val --classes Ship Vehicle
"""
import argparse
import json
import re
import shutil
from pathlib import Path
from urllib.parse import unquote

# File types treated as tiles
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}

# The 8-character hex prefix Label Studio adds to uploaded file names, e.g. "a1b2c3d4-"
HASH_PREFIX = re.compile(r"^[0-9a-f]{8}-")


def parse_args():
    """Read the command-line options.

    Returns:
        argparse.Namespace with url, project_id, from_file, train_dir, val_dir,
        classes and output. Either --from-file, or both --url and --project-id,
        must be given.
    """
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", help="Label Studio base URL, e.g. http://localhost:8080")
    p.add_argument("--project-id", type=int, help="The train/val project's ID")
    p.add_argument("--from-file", type=Path, help="Use a JSON export you downloaded instead of the API")
    p.add_argument("--train-dir", type=Path, required=True, help="Folder of train tiles on disk")
    p.add_argument("--val-dir", type=Path, required=True, help="Folder of val tiles on disk")
    p.add_argument("--classes", nargs="+", required=True,
                   help="Class names in YOLO index order (the first is class 0); must match the "
                        "Label Studio labels exactly")
    p.add_argument("--output", type=Path, default=Path("yolo_dataset"))
    args = p.parse_args()

    if not args.from_file and not (args.url and args.project_id):
        p.error("--url and --project-id are required unless --from-file is given")
    return args


def load_tasks(args):
    """Get the project's tasks with their annotations.

    Args:
        args: Parsed command-line options.

    Returns:
        A list of task dicts in Label Studio's JSON export format. When downloaded from
        the API, a copy is also saved as <output>/labelstudio_export.json.
    """
    if args.from_file:
        return json.loads(args.from_file.read_text(encoding="utf-8"))

    # Imported here so --from-file works without a token
    from ls_auth import LabelStudio
    ls = LabelStudio(args.url)

    # download_all_tasks=false: only tasks that have annotations
    tasks = ls.request("GET", f"/api/projects/{args.project_id}/export",
                       params={"exportType": "JSON", "download_all_tasks": "false"}).json()

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "labelstudio_export.json").write_text(json.dumps(tasks), encoding="utf-8")
    return tasks


def original_name(image_ref):
    """Recover the original tile file name from a task's image reference.

    Handles both ways Label Studio stores images:
        uploaded files:   "/data/upload/1/a1b2c3d4-P2058_x0_y0.png"
        local storage:    "/data/local-files/?d=dataset/sliced/train/P2058_x0_y0.png"

    Args:
        image_ref: The task's data["image"] value.

    Returns:
        The file name without folders or Label Studio's hash prefix,
        e.g. "P2058_x0_y0.png".
    """
    if "d=" in image_ref:
        # Local-files storage: the real path is in the ?d= query parameter
        path = unquote(image_ref.split("d=", 1)[1])
    else:
        # Uploaded file: drop any query string; the name is the last part of the URL
        path = unquote(image_ref.split("?")[0])

    # Normalize Windows backslashes, keep only the file name, then strip the hash prefix
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    return HASH_PREFIX.sub("", name)


def latest_annotation(task):
    """Pick the annotation to export for a task.

    Skipped annotations are ignored. If a tile was annotated more than once,
    the most recently updated annotation wins.

    Args:
        task: One task from the export.

    Returns:
        The annotation dict, or None if the task has no submitted annotation.
    """
    anns = [a for a in task.get("annotations", []) if not a.get("was_cancelled")]
    if not anns:
        return None
    # ISO timestamps sort correctly as strings
    return max(anns, key=lambda a: a.get("updated_at") or a.get("created_at") or "")


def index_local_tiles(train_dir, val_dir):
    """Map each tile file name to its split and location on disk.

    Args:
        train_dir: Folder of train tiles.
        val_dir: Folder of val tiles.

    Returns:
        A dict {file name: (split, path)}, e.g. {"P2058_x0_y0.png": ("train", Path(...))}.
    """
    lookup = {}
    for split, folder in (("train", train_dir), ("val", val_dir)):
        for f in folder.iterdir():
            if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
                lookup[f.name] = (split, f)
    return lookup


def to_yolo_box(value):
    """Convert one Label Studio box to YOLO's normalized centre format.

    Label Studio stores the box's top-left corner and size as percentages (0-100)
    of the image. YOLO wants the box centre and size as fractions (0-1):

        cx = (x + width/2) / 100      cy = (y + height/2) / 100
        w  = width / 100              h  = height / 100

    Args:
        value: The annotation result's "value" dict (x, y, width, height).

    Returns:
        A tuple (cx, cy, w, h), each clamped to 0-1 in case a box was drawn
        slightly past the tile edge.
    """
    w, h = value["width"] / 100, value["height"] / 100
    cx, cy = value["x"] / 100 + w / 2, value["y"] / 100 + h / 2

    def clamp(t):
        return min(max(t, 0.0), 1.0)

    return clamp(cx), clamp(cy), clamp(w), clamp(h)


def annotation_to_label_lines(ann, class_index, tile_name, stats):
    """Turn one annotation's boxes into YOLO label lines.

    Args:
        ann: The annotation dict.
        class_index: Dict {label name: class id}.
        tile_name: Tile file name, used in warnings.
        stats: Counter dict; "unknown_label" is increased for labels not in --classes.

    Returns:
        A list of lines in the form "<class_id> cx cy w h". An empty list means a
        background tile.
    """
    lines = []
    for r in ann.get("result", []):
        # Only rectangle boxes are exported
        if r.get("type") != "rectanglelabels":
            continue

        value = r["value"]
        label = value["rectanglelabels"][0]
        if label not in class_index:
            stats["unknown_label"] += 1
            continue

        # YOLO detection boxes can't be rotated; the unrotated position is used instead
        if value.get("rotation", 0):
            print(f"  warning: rotated box in {tile_name} exported as axis-aligned")

        cx, cy, w, h = to_yolo_box(value)
        lines.append(f"{class_index[label]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
    return lines


def write_data_yaml(output, classes):
    """Write the data.yaml file YOLO needs for training.

    Args:
        output: Dataset folder (data.yaml is written inside it).
        classes: Class names in index order.
    """
    names = "\n".join(f"  {i}: {c}" for i, c in enumerate(classes))
    (output / "data.yaml").write_text(
        f"path: {output.resolve().as_posix()}\n"
        f"train: images/train\n"
        f"val: images/val\n\n"
        f"nc: {len(classes)}\n"
        f"names:\n{names}\n",
        encoding="utf-8")


def main():
    """Export the annotations and build the YOLO dataset, then print a summary."""
    args = parse_args()
    tasks = load_tasks(args)
    lookup = index_local_tiles(args.train_dir, args.val_dir)

    # Class name -> YOLO class id, e.g. {"Ship": 0, "Vehicle": 1}
    class_index = {c: i for i, c in enumerate(args.classes)}

    for split in ("train", "val"):
        (args.output / "images" / split).mkdir(parents=True, exist_ok=True)
        (args.output / "labels" / split).mkdir(parents=True, exist_ok=True)

    stats = {"train": 0, "val": 0, "boxes": 0, "background": 0,
             "unannotated": 0, "not_found": 0, "unknown_label": 0}

    for task in tasks:
        ann = latest_annotation(task)
        if ann is None:
            stats["unannotated"] += 1
            continue

        # Find the matching tile on disk; its folder decides train vs val
        name = original_name(task["data"]["image"])
        if name not in lookup:
            stats["not_found"] += 1
            print(f"  not found locally (skipped): {name}")
            continue
        split, src = lookup[name]

        lines = annotation_to_label_lines(ann, class_index, name, stats)

        # Copy the tile and write its label file (YOLO pairs them by matching file names)
        shutil.copy2(src, args.output / "images" / split / src.name)
        (args.output / "labels" / split / f"{src.stem}.txt").write_text("\n".join(lines), encoding="utf-8")

        stats[split] += 1
        stats["boxes"] += len(lines)
        stats["background"] += (not lines)

    write_data_yaml(args.output, args.classes)

    print(f"train tiles: {stats['train']}, val tiles: {stats['val']}, boxes: {stats['boxes']}, "
          f"background tiles: {stats['background']}")
    print(f"skipped -> unannotated: {stats['unannotated']}, not found locally: {stats['not_found']}, "
          f"unknown labels: {stats['unknown_label']}")
    print(f"Dataset written to {args.output.resolve()}  (train with data={args.output / 'data.yaml'})")


if __name__ == "__main__":
    main()
