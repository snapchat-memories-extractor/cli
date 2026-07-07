from pathlib import Path


def ensure_directories(output_folder: Path, logs_folder: Path) -> None:
    output_folder.mkdir(parents=True, exist_ok=True)
    logs_folder.mkdir(parents=True, exist_ok=True)