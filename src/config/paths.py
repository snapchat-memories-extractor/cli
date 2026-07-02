from pathlib import Path


def _ensure_directories(downloads_folder: Path, logs_folder: Path) -> None:
    downloads_folder.mkdir(parents=True, exist_ok=True)
    logs_folder.mkdir(parents=True, exist_ok=True)
