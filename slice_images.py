"""Slice large images into overlapping tiles with SAHI.

Reads the split lists made by split_dataset.py and writes tiles for every split
(train, val and test) so each one can be loaded into Label Studio as tiles:
  * train/val tiles -> annotated in Label Studio, then used for YOLO training
  * test tiles      -> uploaded to a separate project and pre-annotated by the ML backend

Each split folder also gets tile_metadata.csv, which records where every tile came
from in its original image.

Example (PowerShell):
  python slice_images.py --splits dataset_splits --output dataset/sliced
"""
import argparse
import csv
from pathlib import Path

from PIL import Image
from sahi.slicing import slice_image

Image.MAX_IMAGE_PIXELS = None  # aerial survey images can exceed Pillow's default limit


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--splits", type=Path, default=Path("dataset_splits"),
                   help="Folder containing train.txt, val.txt and test.txt")
    p.add_argument("--output", type=Path, default=Path("dataset/sliced"), help="Output folder for tiles")
    p.add_argument("--tile-size", type=int, default=640)
    p.add_argument("--overlap", type=float, default=0.20, help="Overlap ratio between neighbouring tiles")
    p.add_argument("--split-names", nargs="+", default=["train", "val", "test"])
    args = p.parse_args()

    if args.tile_size <= 0:
        raise ValueError("Tile size must be positive.")
    if not 0 <= args.overlap < 1:
        raise ValueError("Overlap must be between 0 and 1.")

    for split in args.split_names:
        split_file = args.splits / f"{split}.txt"
        if not split_file.exists():
            raise FileNotFoundError(f"Missing split file: {split_file}")

        destination = args.output / split
        destination.mkdir(parents=True, exist_ok=True)
        image_paths = [Path(line.strip()) for line in split_file.read_text(encoding="utf-8").splitlines()
                       if line.strip()]

        with open(destination / "tile_metadata.csv", "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["tile_name", "original_image", "original_width", "original_height",
                             "tile_x", "tile_y", "tile_width", "tile_height"])

            for image_path in image_paths:
                if not image_path.exists():
                    print(f"Skipping missing image: {image_path}")
                    continue

                with Image.open(image_path) as img:
                    img = img.convert("RGB")
                    width, height = img.size
                    result = slice_image(
                        image=img,
                        slice_height=args.tile_size,
                        slice_width=args.tile_size,
                        overlap_height_ratio=args.overlap,
                        overlap_width_ratio=args.overlap,
                        auto_slice_resolution=False,
                    )

                for tile_array, (x, y) in zip(result.images, result.starting_pixels):
                    tile = Image.fromarray(tile_array)
                    tile_name = f"{image_path.stem}_x{x}_y{y}.png"
                    tile.save(destination / tile_name)
                    writer.writerow([tile_name, image_path.name, width, height, x, y, tile.width, tile.height])

                print(f"{split}: {image_path.name} ({width}x{height}) -> {len(result.images)} tiles")

    print(f"Slicing completed. Tiles saved under {args.output.resolve()}")


if __name__ == "__main__":
    main()
