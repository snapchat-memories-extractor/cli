from pathlib import Path

from src.media_dispatcher.image_processor import process_image
from src.media_dispatcher.video_processor import ProcessVideo
from src.memories import Memory

IMAGE_SUFFIXES = {".jpg", ".jpeg"}


def process_media(memory: Memory | None, file_path: Path) -> Path:
    if file_path.suffix.lower() in IMAGE_SUFFIXES:
        return process_image(memory, file_path)
    return ProcessVideo().run(memory, file_path)