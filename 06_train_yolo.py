"""Train a YOLO model on the annotated tiles exported by 05_export_to_yolo.py.

YOLO trains on the train tiles and scores the val tiles after every epoch; the
epoch with the best validation mAP is saved as best.pt.

Example (PowerShell):
  python 06_train_yolo.py --data yolo_dataset/data.yaml --epochs 50 --copy-to-backend
"""
import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", default="yolo_dataset/data.yaml", help="data.yaml written by 05_export_to_yolo.py")
    p.add_argument("--model", default="yolo11n.pt", help="Pretrained starting weights")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--imgsz", type=int, default=640, help="Match the tile size used when slicing")
    p.add_argument("--batch", type=int, default=16)
    p.add_argument("--device", default="cpu", help="'cpu', or a GPU index such as 0")
    p.add_argument("--name", default="tiles", help="Run name; results go to runs/detect/<name>")
    p.add_argument("--copy-to-backend", action="store_true",
                   help="Copy best.pt to yolo_ml_backend/models/best.pt when training finishes")
    args = p.parse_args()

    model = YOLO(args.model)
    model.train(data=args.data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
                device=args.device, name=args.name)

    best = Path(model.trainer.best)
    print(f"\nbest.pt: {best.resolve()}")

    if args.copy_to_backend:
        target = Path(__file__).parent / "yolo_ml_backend" / "models" / "best.pt"
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best, target)
        print(f"Copied to {target.resolve()} (restart the ML backend to load it)")


if __name__ == "__main__":
    main()
