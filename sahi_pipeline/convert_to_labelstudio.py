import json
from pathlib import Path
from PIL import Image

# Input and output paths
INPUT_JSON = Path("sahi_results/0793_predictions.json")
TEST_LIST = Path("dataset_splits/test.txt")
OUTPUT_JSON = Path("sahi_results/0793_labelstudio.json")

# Get original image dimensions
image_path = Path(TEST_LIST.read_text().splitlines()[0].strip())

with Image.open(image_path) as img:
    image_width, image_height = img.size

# Read merged SAHI predictions
data = json.loads(INPUT_JSON.read_text(encoding="utf-8"))

results = []

for i, prediction in enumerate(data["predictions"]):
    x1, y1, x2, y2 = prediction["bbox"]

    results.append({
        "id": f"prediction_{i}",
        "from_name": "label",
        "to_name": "image",
        "type": "rectanglelabels",
        "value": {
            "x": x1 / image_width * 100,
            "y": y1 / image_height * 100,
            "width": (x2 - x1) / image_width * 100,
            "height": (y2 - y1) / image_height * 100,
            "rectanglelabels": [prediction["class"]]
        },
        "score": prediction["confidence"],
        "original_width": image_width,
        "original_height": image_height,
        "image_rotation": 0
    })

# Label Studio prediction structure
output = {
    "predictions": [{
        "model_version": "YOLO11n_SAHI",
        "result": results
    }]
}

OUTPUT_JSON.write_text(
    json.dumps(output, indent=4),
    encoding="utf-8"
)

print(f"Converted {len(results)} predictions.")
print(f"Saved to: {OUTPUT_JSON}")
