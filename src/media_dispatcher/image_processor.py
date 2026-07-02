from pathlib import Path

from src.config import Config
from src.converters import JXLConverter
from src.memories import Memory
from src.media_dispatcher.image_saver import save_image
from src.metadata import ImageMetadataWriter


def process_image(memory: Memory, file_path: Path) -> Path:
    convert_to_jxl = Config.cli_options["convert_to_jxl"]
    write_metadata = Config.cli_options["write_metadata"]

    if write_metadata:
        ImageMetadataWriter(memory, file_path).write_image_metadata()
    else:
        save_image(file_path)

    if convert_to_jxl:
        file_path = JXLConverter(file_path).run()

    return file_path
