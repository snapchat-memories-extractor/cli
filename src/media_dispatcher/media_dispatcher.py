from pathlib import Path
from typing import TYPE_CHECKING

from src.media_dispatcher.image_processor import process_image
from src.media_dispatcher.video_processor import ProcessVideo

if TYPE_CHECKING:
    from src.pipeline.stage_concurrency import StageConcurrency

IMAGE_SUFFIXES = {".jpg", ".jpeg"}


def process_media(
    file_path: Path,
    stage_concurrency: "StageConcurrency | None" = None,
) -> Path:
    if file_path.suffix.lower() in IMAGE_SUFFIXES:
        return process_image(file_path, stage_concurrency)
    return ProcessVideo().run(file_path, stage_concurrency)
