"""Step 2a: split the raw images into training, validation and testing sets.

The images are shuffled with a fixed seed (42), so the same folder always gives the
same split, and divided 70% / 15% / 15%. The split is done on whole images, before
slicing, so tiles from one image never end up in two different sets.

Output: three text files, each listing the full paths of the images in that set:

    dataset_splits/train.txt
    dataset_splits/val.txt
    dataset_splits/test.txt

Example (PowerShell):
    python 02a_split_dataset.py --input data\\pilot --output dataset_splits
"""
import argparse
import random
from pathlib import Path

# File types treated as images
IMAGE_EXTS = {".png", ".jpg", ".jpeg"}

# Fixed seed so the split is reproducible
SEED = 42

# Cumulative cut points: first 70% -> train, next 15% -> val, last 15% -> test
TRAIN_FRACTION = 0.70
VAL_FRACTION = 0.15


def parse_args():
    """Read the command-line options.

    Returns:
        argparse.Namespace with:
            input: folder containing the original images (searched recursively).
            output: folder where train.txt, val.txt and test.txt are written.
    """
    parser = argparse.ArgumentParser(
        description="Split original images into training (70%), validation (15%) and testing (15%) sets."
    )
    parser.add_argument("--input", type=Path, required=True,
                        help="Folder containing the original images")
    parser.add_argument("--output", type=Path, default=Path("dataset_splits"),
                        help="Folder where split lists will be saved")
    return parser.parse_args()


def find_images(source_folder):
    """Find every image in a folder and its subfolders.

    Args:
        source_folder: Folder to search.

    Returns:
        A sorted list of image paths. Sorting first means the shuffle below gives
        the same result on every computer, whatever order the disk lists files in.

    Raises:
        FileNotFoundError: If the folder does not exist.
        ValueError: If the folder contains no supported images.
    """
    if not source_folder.is_dir():
        raise FileNotFoundError(f"Dataset folder not found: {source_folder}")

    images = sorted(
        p for p in source_folder.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )
    if not images:
        raise ValueError("No supported images found in the dataset folder.")
    return images


def split_images(images):
    """Shuffle the images reproducibly and divide them into train, val and test.

    Args:
        images: List of image paths.

    Returns:
        A dict {"train": [...], "val": [...], "test": [...]}. Because the cut points
        are rounded down, any remainder goes to the test set.
    """
    # Shuffle a copy so the caller's list is left untouched
    shuffled = list(images)
    random.seed(SEED)
    random.shuffle(shuffled)

    total = len(shuffled)
    train_end = int(total * TRAIN_FRACTION)                  # e.g. 10 images -> 7
    val_end = int(total * (TRAIN_FRACTION + VAL_FRACTION))   # e.g. 10 images -> 8

    return {
        "train": shuffled[:train_end],
        "val": shuffled[train_end:val_end],
        "test": shuffled[val_end:],
    }


def save_splits(splits, output_folder):
    """Write one text file per split, listing the absolute path of each image.

    Absolute paths let 02b_slice_images.py find the images from any working folder.

    Args:
        splits: Dict returned by split_images().
        output_folder: Folder to write train.txt, val.txt and test.txt into.
    """
    output_folder.mkdir(parents=True, exist_ok=True)

    for split_name, split_images_list in splits.items():
        output_file = output_folder / f"{split_name}.txt"
        with open(output_file, "w", encoding="utf-8") as f:
            for image in split_images_list:
                f.write(str(image.resolve()) + "\n")
        print(f"{split_name}: {len(split_images_list)} images")


def main():
    """Run the split: find images, shuffle and divide them, and save the lists."""
    args = parse_args()
    images = find_images(args.input)
    splits = split_images(images)
    save_splits(splits, args.output)

    print(f"Total images: {len(images)}")
    print(f"Split lists saved to: {args.output.resolve()}")


if __name__ == "__main__":
    main()
