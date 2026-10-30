from pathlib import Path
import argparse
import random
import shutil

parser = argparse.ArgumentParser(
    description="Prepare a person-only YOLO dataset from COCO128."
)

parser.add_argument(
    "--source",
    type=Path,
    required=True,
    help="Root directory containing COCO128 images and labels"
)

parser.add_argument(
    "--output",
    type=Path,
    default=Path("person_dataset"),
    help="Output dataset directory"
)

args = parser.parse_args()

source = args.source
output = args.output

image_source = source / "images" / "train2017"
label_source = source / "labels" / "train2017"

if not image_source.is_dir():
    raise FileNotFoundError(
        f"Image directory not found: {image_source}"
    )

if not label_source.is_dir():
    raise FileNotFoundError(
        f"Label directory not found: {label_source}"
    )

images = sorted(image_source.glob("*.jpg"))

if not images:
    raise ValueError("No JPG images found.")

random.seed(42)
random.shuffle(images)

split_point = int(len(images) * 0.8)

splits = {
    "train": images[:split_point],
    "val": images[split_point:]
}

for split, image_list in splits.items():

    image_folder = output / "images" / split
    label_folder = output / "labels" / split

    image_folder.mkdir(parents=True, exist_ok=True)
    label_folder.mkdir(parents=True, exist_ok=True)

    for image_path in image_list:

        label_path = (
            label_source / f"{image_path.stem}.txt"
        )

        person_labels = []

        if label_path.exists():
            for line in label_path.read_text(
                encoding="utf-8"
            ).splitlines():

                values = line.split()

                if values and values[0] == "0":
                    person_labels.append(line)

        shutil.copy2(
            image_path,
            image_folder / image_path.name
        )

        output_label = (
            label_folder / f"{image_path.stem}.txt"
        )

        output_label.write_text(
            "\n".join(person_labels),
            encoding="utf-8"
        )

    print(f"{split}: {len(image_list)} images")

print("Person dataset preparation completed.")
