from pathlib import Path
from typing import TYPE_CHECKING

from src.config import Config
from src.conversion import JXLConverter
from src.memories import Memory
from src.metadata import ImageMetadataWriter

if TYPE_CHECKING:
    from src.pipeline.stage_concurrency import StageConcurrency


def process_image(
    memory: Memory | None,
    file_path: Path,
    stage_concurrency: "StageConcurrency | None" = None,
) -> Path:
    convert_to_jxl = Config.cli_options["convert_to_jxl"]
    write_metadata = Config.cli_options["write_metadata"]

    if write_metadata and memory is not None:
        _write_image_metadata(memory, file_path, stage_concurrency)

    if convert_to_jxl:
        file_path = _convert_to_jxl(file_path, stage_concurrency)

    return file_path


def _write_image_metadata(
    memory: Memory,
    file_path: Path,
    stage_concurrency: "StageConcurrency | None",
) -> None:
    if stage_concurrency is None:
        ImageMetadataWriter(memory, file_path).write_image_metadata()
        return

    with stage_concurrency.gps_writer_slot():
        ImageMetadataWriter(memory, file_path).write_image_metadata()


def _convert_to_jxl(
    file_path: Path,
    stage_concurrency: "StageConcurrency | None",
) -> Path:
    if stage_concurrency is None:
        return JXLConverter(file_path).run()

    with stage_concurrency.jxl_converter_slot():
        return JXLConverter(file_path).run()
