from pathlib import Path
from PIL import Image
import math

# Read first original test image
test_list = Path("dataset_splits/test.txt")
image_path = Path(test_list.read_text().splitlines()[0].strip())

output_dir = Path("tiled_viewer/0793_files")
output_dir.mkdir(parents=True, exist_ok=True)

tile_size = 256
overlap = 1

with Image.open(image_path) as original:
    original = original.convert("RGB")
    width, height = original.size

    max_level = math.ceil(math.log2(max(width, height)))

    for level in range(max_level + 1):
        scale = 2 ** (max_level - level)
        level_width = math.ceil(width / scale)
        level_height = math.ceil(height / scale)

        level_image = original.resize(
            (level_width, level_height),
            Image.Resampling.LANCZOS
        )

        level_dir = output_dir / str(level)
        level_dir.mkdir(exist_ok=True)

        cols = math.ceil(level_width / tile_size)
        rows = math.ceil(level_height / tile_size)

        for row in range(rows):
            for col in range(cols):
                left = max(0, col * tile_size - (overlap if col else 0))
                top = max(0, row * tile_size - (overlap if row else 0))
                right = min(level_width, (col + 1) * tile_size + overlap)
                bottom = min(level_height, (row + 1) * tile_size + overlap)

                tile = level_image.crop((left, top, right, bottom))
                tile.save(level_dir / f"{col}_{row}.jpg", quality=90)

dzi = f'''<?xml version="1.0" encoding="UTF-8"?>
<Image TileSize="{tile_size}" Overlap="{overlap}"
       Format="jpg"
       xmlns="http://schemas.microsoft.com/deepzoom/2008">
    <Size Width="{width}" Height="{height}" />
</Image>'''

Path("tiled_viewer/0793.dzi").write_text(dzi, encoding="utf-8")

print(f"Created Deep Zoom tiles for {image_path.name}")
print(f"Original dimensions: {width} x {height}")
print(f"Maximum zoom level: {max_level}")
print("DZI file: tiled_viewer/0793.dzi")
