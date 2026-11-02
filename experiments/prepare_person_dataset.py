"""Early experiment: build a person-only YOLO dataset from COCO128.

COCO128 labels 80 classes. This keeps every image but only the "person" boxes (class 0),
then splits the images 80/20 into train and val. It was used to try single-class
training before the SAHI large-image pipeline (02a-06) existed.

Input layout (the COCO128 download):
    <source>/images/train2017/*.jpg
    <source>/labels/train2017/*.txt   YOLO format: <class_id> cx cy w h per line

Output layout:
    <output>/images/{train,val}/*.jpg
    <output>/labels/{train,val}/*.txt  person boxes only (empty file = no person)

Example:
    python experiments/prepare_person_dataset.py --source datasets/coco128 --output person_dataset
"""
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

# COCO128 keeps all its images and labels in a single "train2017" folder
image_source = source / "images" / "train2017"
label_source = source / "labels" / "train2017"

# Fail early with a clear message if --source doesn't point at COCO128
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

# Shuffle with a fixed seed so the same images land in train/val on every run
random.seed(42)
random.shuffle(images)

# 80% train, 20% val
split_point = int(len(images) * 0.8)

splits = {
    "train": images[:split_point],
    "val": images[split_point:]
}

for split, image_list in splits.items():

    image_folder = output / "images" / split
    label_folder = output / "labels" / split

    # Create the output folders for this split (no error if they already exist)
    image_folder.mkdir(parents=True, exist_ok=True)
    label_folder.mkdir(parents=True, exist_ok=True)

    for image_path in image_list:

        label_path = (
            label_source / f"{image_path.stem}.txt"
        )

        # Collect only the person boxes from this image's label file
        person_labels = []

        if label_path.exists():
            for line in label_path.read_text(
                encoding="utf-8"
            ).splitlines():

                values = line.split()

                # The first value is the class ID; 0 is "person" in COCO
                if values and values[0] == "0":
                    person_labels.append(line)

        # Copy every image, even ones with no person: they become background
        # examples that teach the model what "no person" looks like
        shutil.copy2(
            image_path,
            image_folder / image_path.name
        )

        output_label = (
            label_folder / f"{image_path.stem}.txt"
        )

        # Write the person boxes (an empty file if there were none)
        output_label.write_text(
            "\n".join(person_labels),
            encoding="utf-8"
        )

    print(f"{split}: {len(image_list)} images")

print("Person dataset preparation completed.")
