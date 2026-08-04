from pathlib import Path

from src.config import Config
from src.logger import log


def scan_memory_files() -> list[Path]:
    try:
        return sorted(
            path
            for path in Config.memories_folder.iterdir()
            if path.is_file()
        )
    except OSError as error:
        log(
            f"Failed to scan memories folder at {Config.memories_folder}: {error}",
            "error",
            "SCAN",
        )
        raise

def overlay_phase_items() -> list[Path]:
        return [path for path in scan_memory_files() if path.stem.endswith("-main")]
