"""Early experiment: check that YOLO training runs at all on this machine.

Trains the smallest YOLO11 model (yolo11n) for one epoch on COCO128, the 128-image
sample of COCO that Ultralytics downloads automatically. The result isn't a useful
model; it only confirms that ultralytics, the dataset download and the training loop
work before the real pipeline (02a-06) is used.

Run from the repo root:
    python experiments/train_test.py
Output goes to training/initial_test/ (weights, plots, metrics).
"""
from ultralytics import YOLO

# Pretrained YOLO11 nano weights; downloaded on first use

model = YOLO("yolo11n.pt")

model.train(
    data="coco128.yaml",  # dataset config bundled with ultralytics; downloads COCO128
    epochs=1,             # one pass is enough to prove training works
    imgsz=320,            # small images keep a CPU run to a few minutes
    batch=4,              # small batch so it fits in memory without a GPU
    device="cpu",         # no GPU needed
    workers=0,            # load data in the main process (avoids Windows multiprocessing issues)
    project="training",   # results go to training/initial_test/
    name="initial_test"
)