from pathlib import Path
from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction
import json

# Paths
MODEL_PATH = "runs/detect/runs/div2k/car_person_ship/weights/best.pt"
TEST_LIST = Path("dataset_splits/test.txt")
OUTPUT_DIR = Path("sahi_results")
OUTPUT_DIR.mkdir(exist_ok=True)

# Load first original test image
image_path = Path(TEST_LIST.read_text().splitlines()[0].strip())
print(f"Processing: {image_path.name}")

# Load trained YOLO model
detection_model = AutoDetectionModel.from_pretrained(
    model_type="ultralytics",
    model_path=MODEL_PATH,
    confidence_threshold=0.25,
    device="cpu",
)

# SAHI slicing, detection, and merging
result = get_sliced_prediction(
    str(image_path),
    detection_model,
    slice_height=640,
    slice_width=640,
    overlap_height_ratio=0.2,
    overlap_width_ratio=0.2,
    postprocess_type="GREEDYNMM",
    postprocess_match_metric="IOS",
    postprocess_match_threshold=0.3,
    postprocess_class_agnostic=False,
)

# Results are expressed in original-image coordinates
print(f"Merged detections: {len(result.object_prediction_list)}")

for prediction in result.object_prediction_list:
    print(
        prediction.category.name,
        prediction.bbox.to_xyxy(),
        f"confidence={prediction.score.value:.3f}"
    )

# Save visual result
result.export_visuals(
    export_dir=str(OUTPUT_DIR),
    file_name="test_image_1"
)

print(f"Visualization saved to: {OUTPUT_DIR.resolve()}")


# Save merged predictions as JSON for the tiled viewer
predictions = []

for prediction in result.object_prediction_list:
    predictions.append({
        "class": prediction.category.name,
        "confidence": float(prediction.score.value),
        "bbox": [float(v) for v in prediction.bbox.to_xyxy()]
    })

output_json = OUTPUT_DIR / "0793_predictions.json"

with open(output_json, "w", encoding="utf-8") as f:
    json.dump({
        "image": image_path.name,
        "predictions": predictions
    }, f, indent=4)

print(f"Saved {len(predictions)} predictions to {output_json}")


