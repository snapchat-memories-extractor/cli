from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg"}
VIDEO_SUFFIXES = {".mp4"}


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_SUFFIXES
