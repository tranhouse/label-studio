"""Export annotations from Label Studio and build a YOLO dataset from your local tiles.

Label Studio renames uploaded files ("0793_x0_y0.png" -> "a1b2c3d4-0793_x0_y0.png"),
so this script maps each task back to the original tile on disk, uses the folder it
lives in (train or val) as its split, and writes YOLO label files.

Tiles annotated with no boxes (submitted empty) become background images, which is
what you want for aerial imagery. Tasks with no submitted annotation are skipped.

Example (PowerShell):
  python 05_export_to_yolo.py --url http://ci-cdos-labelstudio-dev.ent.dfo-mpo.ca:8080 --project-id 61 `
      --train-dir dataset/sliced/train --val-dir dataset/sliced/val --classes Car Person Ship
"""
import argparse
import json
import re
import shutil
from pathlib import Path
from urllib.parse import unquote

HASH_PREFIX = re.compile(r"^[0-9a-f]{8}-")


def original_name(image_ref):
    name = unquote(image_ref.split("?")[0].replace("\\", "/").rsplit("/", 1)[-1])
    if "d=" in image_ref:  # local-files storage: /data/local-files/?d=path/to/tile.png
        name = unquote(image_ref.split("d=", 1)[1]).replace("\\", "/").rsplit("/", 1)[-1]
    return HASH_PREFIX.sub("", name)


def latest_annotation(task):
    anns = [a for a in task.get("annotations", []) if not a.get("was_cancelled")]
    if not anns:
        return None
    return max(anns, key=lambda a: a.get("updated_at") or a.get("created_at") or "")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", help="Label Studio base URL")
    p.add_argument("--project-id", type=int)
    p.add_argument("--from-file", type=Path, help="Use a JSON export you downloaded instead of the API")
    p.add_argument("--train-dir", type=Path, required=True)
    p.add_argument("--val-dir", type=Path, required=True)
    p.add_argument("--classes", nargs="+", required=True, help="Class names in YOLO index order")
    p.add_argument("--output", type=Path, default=Path("yolo_dataset"))
    args = p.parse_args()

    if args.from_file:
        tasks = json.loads(args.from_file.read_text(encoding="utf-8"))
    else:
        if not (args.url and args.project_id):
            p.error("--url and --project-id are required unless --from-file is given")
        from ls_auth import LabelStudio
        ls = LabelStudio(args.url)
        tasks = ls.request("GET", f"/api/projects/{args.project_id}/export",
                           params={"exportType": "JSON", "download_all_tasks": "false"}).json()
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "labelstudio_export.json").write_text(json.dumps(tasks), encoding="utf-8")

    lookup = {}
    for split, folder in (("train", args.train_dir), ("val", args.val_dir)):
        for f in folder.iterdir():
            if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
                lookup[f.name] = (split, f)

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
        name = original_name(task["data"]["image"])
        if name not in lookup:
            stats["not_found"] += 1
            print(f"  not found locally (skipped): {name}")
            continue
        split, src = lookup[name]

        lines = []
        for r in ann.get("result", []):
            if r.get("type") != "rectanglelabels":
                continue
            v = r["value"]
            label = v["rectanglelabels"][0]
            if label not in class_index:
                stats["unknown_label"] += 1
                continue
            if v.get("rotation", 0):
                print(f"  warning: rotated box in {name} exported as axis-aligned")
            # Label Studio: top-left x/y and size in percent of image -> YOLO: normalized center + size
            w, h = v["width"] / 100, v["height"] / 100
            cx, cy = v["x"] / 100 + w / 2, v["y"] / 100 + h / 2
            clamp = lambda t: min(max(t, 0.0), 1.0)
            lines.append(f"{class_index[label]} {clamp(cx):.6f} {clamp(cy):.6f} {clamp(w):.6f} {clamp(h):.6f}")

        shutil.copy2(src, args.output / "images" / split / src.name)
        (args.output / "labels" / split / f"{src.stem}.txt").write_text("\n".join(lines), encoding="utf-8")
        stats[split] += 1
        stats["boxes"] += len(lines)
        stats["background"] += (not lines)

    names = "\n".join(f"  {i}: {c}" for i, c in enumerate(args.classes))
    (args.output / "data.yaml").write_text(
        f"path: {args.output.resolve().as_posix()}\ntrain: images/train\nval: images/val\n\n"
        f"nc: {len(args.classes)}\nnames:\n{names}\n", encoding="utf-8")

    print(f"train tiles: {stats['train']}, val tiles: {stats['val']}, boxes: {stats['boxes']}, "
          f"background tiles: {stats['background']}")
    print(f"skipped -> unannotated: {stats['unannotated']}, not found locally: {stats['not_found']}, "
          f"unknown labels: {stats['unknown_label']}")
    print(f"Dataset written to {args.output.resolve()}  (train with data={args.output / 'data.yaml'})")


if __name__ == "__main__":
    main()
