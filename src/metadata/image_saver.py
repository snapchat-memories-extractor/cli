from pathlib import Path

from PIL import Image

from src.config import Config


def save_image(file_path: Path, exif_bytes: bytes | None = None) -> None:
    quality = Config.cli_options["jpeg_quality"]

    with Image.open(file_path) as image:
        if exif_bytes is not None:
            image.save(str(file_path), quality=quality, exif=exif_bytes)
        else:
            image.save(str(file_path), quality=quality)
