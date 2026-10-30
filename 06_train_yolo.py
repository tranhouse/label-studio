"""Step 6: train a YOLO model on the annotated tiles exported by 05_export_to_yolo.py.

How training works:
  * Each epoch is one full pass over the train tiles; the model learns from them.
  * After each epoch, YOLO scores the val tiles (mAP). The model does not learn from
    them; they are only used to measure it.
  * The epoch with the best validation score is saved as best.pt, and the final
    epoch as last.pt, in runs/detect/<name>/weights/.

Example (PowerShell):
    python 06_train_yolo.py --data yolo_dataset/data.yaml --epochs 50 --copy-to-backend
"""
import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

# Where the ML backend loads the model from (matches model_path="best.pt" in the labeling config)
BACKEND_MODEL_PATH = Path(__file__).parent / "yolo_ml_backend" / "models" / "best.pt"


def parse_args():
    """Read the command-line options.

    Returns:
        argparse.Namespace with data, model, epochs, imgsz, batch, device, name and
        copy_to_backend.
    """
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default="yolo_dataset/data.yaml", help="data.yaml written by 05_export_to_yolo.py")
    p.add_argument("--model", default="yolo11n.pt",
                   help="Pretrained starting weights (downloaded automatically on first use)")
    p.add_argument("--epochs", type=int, default=50, help="Number of passes over the training tiles")
    p.add_argument("--imgsz", type=int, default=640, help="Match the tile size used when slicing")
    p.add_argument("--batch", type=int, default=16, help="Tiles per training step; lower it if memory runs out")
    p.add_argument("--device", default="cpu", help="'cpu', or a GPU index such as 0")
    p.add_argument("--name", default="tiles",
                   help="Run name; results go to runs/detect/<name> (a number is added if it already exists)")
    p.add_argument("--copy-to-backend", action="store_true",
                   help="Copy best.pt to yolo_ml_backend/models/best.pt when training finishes")
    return p.parse_args()


def train(args):
    """Train the model and return the path of the best checkpoint.

    Starting from pretrained weights (transfer learning) lets a small dataset give
    usable results much faster than training from scratch.

    Args:
        args: Parsed command-line options.

    Returns:
        Path to best.pt for this run.
    """
    model = YOLO(args.model)
    model.train(data=args.data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
                device=args.device, name=args.name)

    # The trainer records where it saved best.pt for this run
    return Path(model.trainer.best)


def copy_to_backend(best):
    """Copy best.pt into the ML backend's models folder.

    The backend loads the model when it first needs it and keeps it in memory, so it
    must be restarted to pick up the new file.

    Args:
        best: Path to the trained best.pt.
    """
    BACKEND_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, BACKEND_MODEL_PATH)
    print(f"Copied to {BACKEND_MODEL_PATH.resolve()} (restart the ML backend to load it)")


def main():
    """Train, report where best.pt was saved, and optionally copy it to the backend."""
    args = parse_args()
    best = train(args)
    print(f"\nbest.pt: {best.resolve()}")

    if args.copy_to_backend:
        copy_to_backend(best)


if __name__ == "__main__":
    main()
