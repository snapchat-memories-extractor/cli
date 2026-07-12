from pathlib import Path

from src.config import Config


def scan_memory_files() -> list[Path]:
    return sorted(
        path
        for path in Config.memories_folder.iterdir()
        if path.is_file()
    )
