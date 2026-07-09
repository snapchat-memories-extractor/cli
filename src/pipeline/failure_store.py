import shutil
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path

from src.config import Config
from src.logger import log


class FailureStore:
    def __init__(self) -> None:
        self.root = Config.failures_folder

    def move_file(self, file_path: Path) -> bool:
        if not file_path.is_file():
            return False

        self.root.mkdir(parents=True, exist_ok=True)
        failure_path = self._available_path(self.root / file_path.name, "failed")
        shutil.move(str(file_path), str(failure_path))
        log(f"Moved failed file to {failure_path}: {file_path}", "warning")
        return True

    def move_files(self, file_paths: Iterable[Path]) -> None:
        for file_path in file_paths:
            self.move_file(file_path)

    def restore_all(self) -> None:
        if not self.root.exists():
            return

        restored = 0
        for failure_path in sorted(self.root.iterdir()):
            if failure_path.is_file():
                restore_path = self._available_path(
                    Config.memories_folder / failure_path.name,
                    "restored",
                )
                shutil.move(str(failure_path), str(restore_path))
                restored += 1

        with suppress(OSError):
            self.root.rmdir()

        if restored:
            log(f"Restored {restored} failed file(s) to memories folder.", "info")

    @staticmethod
    def _available_path(path: Path, label: str) -> Path:
        if not path.exists():
            return path

        counter = 1
        while True:
            candidate = path.with_name(f"{path.stem}-{label}-{counter}{path.suffix}")
            if not candidate.exists():
                return candidate
            counter += 1
