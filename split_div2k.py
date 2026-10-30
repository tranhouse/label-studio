from pathlib import Path
import random
import argparse

# Configure command-line arguments
parser = argparse.ArgumentParser(
    description="Split original images into training, validation, and testing sets."
)

parser.add_argument(
    "--input",
    type=Path,
    required=True,
    help="Folder containing the original images"
)

parser.add_argument(
    "--output",
    type=Path,
    default=Path("dataset_splits"),
    help="Folder where split lists will be saved"
)

args = parser.parse_args()

source_folder = args.input
output_folder = args.output

# Check input directory
if not source_folder.is_dir():
    raise FileNotFoundError(
        f"Dataset folder not found: {source_folder}"
    )

# Find original images
images = sorted(
    p for p in source_folder.rglob("*")
    if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg"}
)

if not images:
    raise ValueError("No supported images found in the dataset folder.")

# Shuffle reproducibly
random.seed(42)
random.shuffle(images)

total = len(images)

# Split 70% training, 15% validation, 15% testing
train_end = int(total * 0.70)
val_end = int(total * 0.85)

splits = {
    "train": images[:train_end],
    "val": images[train_end:val_end],
    "test": images[val_end:]
}

# Create output directory
output_folder.mkdir(parents=True, exist_ok=True)

# Save the split lists
for split_name, split_images in splits.items():
    output_file = output_folder / f"{split_name}.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        for image in split_images:
            f.write(str(image.resolve()) + "\n")

    print(f"{split_name}: {len(split_images)} images")

print(f"Total images: {total}")
print(f"Split lists saved to: {output_folder.resolve()}")
