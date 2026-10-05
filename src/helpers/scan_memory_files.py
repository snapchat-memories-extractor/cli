from pathlib import Path

from src.config import Config
from src.logger import log


def scan_memory_files() -> list[Path]:
    return _scan_files(Config.memories_folder, "memories folder")


def scan_output_files() -> list[Path]:
    return [
        path
        for path in _scan_files(Config.output_folder, "output folder")
        if not path.stem.endswith("-overlay")
    ]


def overlay_phase_items() -> list[Path]:
    return [
        path
        for path in scan_memory_files()
        if path.stem.endswith(("-main", "-overlaid"))
    ]


def _scan_files(folder: Path, description: str) -> list[Path]:
    try:
        return sorted(
            path
            for path in folder.iterdir()
            if path.is_file()
        )
    except OSError as error:
        log(
            f"Failed to scan {description} at {folder}: {error}",
            "error",
            "SCAN",
        )
        raise
