from ultralytics import YOLO

# Load pretrained YOLO11 model
model = YOLO("yolo11n.pt")

# Train on our annotated DIV2K image tiles
results = model.train(
    data="yolo_dataset/data.yaml",
    epochs=30,
    imgsz=640,
    batch=8,
    device="cpu",
    project="runs/div2k",
    name="car_person_ship",
    exist_ok=True
)

print("YOLO training completed!")
