"""Step 2b: slice large images into overlapping tiles with SAHI.

Reads the split lists made by 02a_split_dataset.py and cuts every image into
640 x 640 tiles (by default) with 20% overlap. All three splits are sliced:

  * train/val tiles -> annotated in Label Studio, then used for YOLO training
  * test tiles      -> uploaded to a separate project and pre-annotated by the ML backend

Tiles are named "<image>_x<left>_y<top>.png", where left/top is the tile's position
in the original image, e.g. "P2058_x512_y1024.png". Each split folder also gets
tile_metadata.csv, which records the same information as a table.

Output:
    dataset/sliced/train/   *.png + tile_metadata.csv
    dataset/sliced/val/     *.png + tile_metadata.csv
    dataset/sliced/test/    *.png + tile_metadata.csv

Example (PowerShell):
    python 02b_slice_images.py --splits dataset_splits --output dataset/sliced
"""
import argparse
import csv
from pathlib import Path

from PIL import Image
from sahi.slicing import slice_image

# Pillow refuses very large images by default (a safety check against "decompression
# bombs"). Aerial survey images can legitimately be that big, so the limit is removed.
Image.MAX_IMAGE_PIXELS = None

# Column headings for tile_metadata.csv
METADATA_COLUMNS = ["tile_name", "original_image", "original_width", "original_height",
                    "tile_x", "tile_y", "tile_width", "tile_height"]


def parse_args():
    """Read and check the command-line options.

    Returns:
        argparse.Namespace with splits, output, tile_size, overlap and split_names.

    Raises:
        ValueError: If the tile size or overlap is out of range.
    """
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--splits", type=Path, default=Path("dataset_splits"),
                   help="Folder containing train.txt, val.txt and test.txt")
    p.add_argument("--output", type=Path, default=Path("dataset/sliced"), help="Output folder for tiles")
    p.add_argument("--tile-size", type=int, default=640,
                   help="Tile width and height in pixels; should match the YOLO training size (imgsz)")
    p.add_argument("--overlap", type=float, default=0.20,
                   help="Overlap ratio between neighbouring tiles (0.2 = 20%%)")
    p.add_argument("--split-names", nargs="+", default=["train", "val", "test"],
                   help="Which split lists to slice")
    args = p.parse_args()

    if args.tile_size <= 0:
        raise ValueError("Tile size must be positive.")
    if not 0 <= args.overlap < 1:
        raise ValueError("Overlap must be between 0 and 1.")
    return args


def read_split_list(split_file):
    """Read a split list (train.txt, val.txt or test.txt) into image paths.

    Args:
        split_file: Path to the text file, one image path per line.

    Returns:
        A list of Path objects, with blank lines ignored.

    Raises:
        FileNotFoundError: If the split file does not exist (run 02a first).
    """
    if not split_file.exists():
        raise FileNotFoundError(f"Missing split file: {split_file}")
    lines = split_file.read_text(encoding="utf-8").splitlines()
    return [Path(line.strip()) for line in lines if line.strip()]


def slice_one_image(image_path, destination, writer, tile_size, overlap):
    """Cut one image into tiles, save them, and record each tile in the metadata CSV.

    SAHI works out the tile positions. Where the image doesn't divide evenly, the last
    row and column of tiles are shifted inward so every tile stays full size. An image
    smaller than the tile size becomes a single tile of its own size.

    Args:
        image_path: The original image.
        destination: Folder to save the tiles in.
        writer: csv.writer for this split's tile_metadata.csv.
        tile_size: Tile width and height in pixels.
        overlap: Overlap ratio between neighbouring tiles.

    Returns:
        The number of tiles written, or 0 if the image file is missing.
    """
    if not image_path.exists():
        print(f"Skipping missing image: {image_path}")
        return 0

    with Image.open(image_path) as img:
        # Convert to RGB so greyscale, palette and RGBA images all produce standard tiles
        img = img.convert("RGB")
        width, height = img.size

        # auto_slice_resolution=False makes SAHI use exactly the tile size and overlap given,
        # instead of choosing its own based on the image size
        result = slice_image(
            image=img,
            slice_height=tile_size,
            slice_width=tile_size,
            overlap_height_ratio=overlap,
            overlap_width_ratio=overlap,
            auto_slice_resolution=False,
        )

    # result.images holds the tiles as arrays; result.starting_pixels holds each tile's
    # top-left corner (x, y) in the original image, in the same order
    for tile_array, (x, y) in zip(result.images, result.starting_pixels):
        tile = Image.fromarray(tile_array)
        tile_name = f"{image_path.stem}_x{x}_y{y}.png"
        tile.save(destination / tile_name)
        writer.writerow([tile_name, image_path.name, width, height, x, y, tile.width, tile.height])

    print(f"  {image_path.name} ({width}x{height}) -> {len(result.images)} tiles")
    return len(result.images)


def slice_split(split, splits_folder, output_folder, tile_size, overlap):
    """Slice every image listed in one split and write its tile_metadata.csv.

    Args:
        split: Split name, e.g. "train".
        splits_folder: Folder containing the split lists.
        output_folder: Root output folder; tiles go into <output_folder>/<split>/.
        tile_size: Tile width and height in pixels.
        overlap: Overlap ratio between neighbouring tiles.
    """
    image_paths = read_split_list(splits_folder / f"{split}.txt")

    destination = output_folder / split
    destination.mkdir(parents=True, exist_ok=True)

    print(f"{split}: {len(image_paths)} images")
    total_tiles = 0
    with open(destination / "tile_metadata.csv", "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(METADATA_COLUMNS)
        for image_path in image_paths:
            total_tiles += slice_one_image(image_path, destination, writer, tile_size, overlap)
    print(f"{split}: {total_tiles} tiles in total")


def main():
    """Slice every requested split (train, val and test by default)."""
    args = parse_args()
    for split in args.split_names:
        slice_split(split, args.splits, args.output, args.tile_size, args.overlap)
    print(f"Slicing completed. Tiles saved under {args.output.resolve()}")


if __name__ == "__main__":
    main()
