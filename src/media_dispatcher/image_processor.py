from pathlib import Path

from src.config import Config
from src.converters import JXLConverter
from src.memories import Memory
from src.metadata import ImageMetadataWriter


def process_image(memory: Memory | None, file_path: Path) -> Path:
    convert_to_jxl = Config.cli_options["convert_to_jxl"]
    write_metadata = Config.cli_options["write_metadata"]

    if write_metadata and memory is not None:
        ImageMetadataWriter(memory, file_path).write_image_metadata()

    if convert_to_jxl:
        file_path = JXLConverter(file_path).run()

    return file_path