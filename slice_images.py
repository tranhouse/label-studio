from pathlib import Path
from PIL import Image
import csv
import argparse

parser = argparse.ArgumentParser(
    description="Slice large images into overlapping tiles."
)

parser.add_argument(
    "--splits",
    type=Path,
    default=Path("dataset_splits"),
    help="Folder containing train.txt, val.txt, and test.txt"
)

parser.add_argument(
    "--output",
    type=Path,
    default=Path("dataset/sliced"),
    help="Output folder for sliced images"
)

parser.add_argument(
    "--tile-size",
    type=int,
    default=640
)

parser.add_argument(
    "--overlap",
    type=float,
    default=0.20
)

args = parser.parse_args()

tile_size = args.tile_size
overlap = args.overlap

if tile_size <= 0:
    raise ValueError("Tile size must be positive.")

if not 0 <= overlap < 1:
    raise ValueError("Overlap must be between 0 and 1.")

step = int(tile_size * (1 - overlap))

if step < 1:
    raise ValueError("Overlap produces an invalid step size.")

Image.MAX_IMAGE_PIXELS = None


def tile_positions(length, tile_size, step):
    """Return tile starting positions with full-sized edge tiles."""
    if length <= tile_size:
        return [0]

    positions = list(range(0, length - tile_size + 1, step))
    last = length - tile_size

    if positions[-1] != last:
        positions.append(last)

    return positions


for split in ["train", "val", "test"]:

    split_file = args.splits / f"{split}.txt"

    if not split_file.exists():
        raise FileNotFoundError(
            f"Missing split file: {split_file}"
        )

    destination = args.output / split
    destination.mkdir(parents=True, exist_ok=True)

    with open(split_file, "r", encoding="utf-8") as f:
        image_paths = [
            Path(line.strip())
            for line in f
            if line.strip()
        ]

    metadata_file = destination / "tile_metadata.csv"

    with open(metadata_file, "w", newline="", encoding="utf-8") as csvfile:

        writer = csv.writer(csvfile)

        writer.writerow([
            "tile_name",
            "original_image",
            "original_width",
            "original_height",
            "tile_x",
            "tile_y",
            "tile_width",
            "tile_height"
        ])

        for image_path in image_paths:

            if not image_path.exists():
                print(f"Skipping missing image: {image_path}")
                continue

            with Image.open(image_path) as img:

                width, height = img.size

                x_positions = tile_positions(
                    width, tile_size, step
                )

                y_positions = tile_positions(
                    height, tile_size, step
                )

                tile_count = 0

                for y in y_positions:
                    for x in x_positions:

                        tile = img.crop((
                            x,
                            y,
                            min(x + tile_size, width),
                            min(y + tile_size, height)
                        ))

                        tile_name = (
                            f"{image_path.stem}_x{x}_y{y}.png"
                        )

                        tile.save(destination / tile_name)

                        writer.writerow([
                            tile_name,
                            image_path.name,
                            width,
                            height,
                            x,
                            y,
                            tile.width,
                            tile.height
                        ])

                        tile_count += 1

                print(
                    f"{split}: {image_path.name} -> "
                    f"{tile_count} tiles"
                )

print("Slicing completed.")
