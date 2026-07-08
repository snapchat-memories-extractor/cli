from pathlib import Path
from typing import TYPE_CHECKING

from src.config import Config
from src.conversion.jxl_converter import JXLConverter

if TYPE_CHECKING:
    from src.pipeline.stage_concurrency import StageConcurrency


def process_image(
    file_path: Path,
    stage_concurrency: "StageConcurrency | None" = None,
) -> Path:
    if Config.cli_options["convert_to_jxl"]:
        file_path = _convert_to_jxl(file_path, stage_concurrency)

    return file_path


def _convert_to_jxl(
    file_path: Path,
    stage_concurrency: "StageConcurrency | None",
) -> Path:
    if stage_concurrency is None:
        return JXLConverter(file_path).run()

    with stage_concurrency.jxl_converter_slot():
        return JXLConverter(file_path).run()
