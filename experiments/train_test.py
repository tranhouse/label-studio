from ultralytics import YOLO

model = YOLO("yolo11n.pt")

model.train(
    data="coco128.yaml",
    epochs=1,
    imgsz=320,
    batch=4,
    device="cpu",
    workers=0,
    project="training",
    name="initial_test"
)