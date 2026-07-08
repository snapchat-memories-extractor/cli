import shutil
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path

from src.config import Config
from src.logger import log


class FailureStore:
    def __init__(self) -> None:
        self.root = Config.failures_folder
        self._restore_targets: dict[Path, Path] = {}

    def move_file(self, file_path: Path) -> bool:
        if not file_path.is_file():
            return False

        failure_path = self._available_path(
            self.root / self._relative_path(file_path),
            "failed",
        )
        failure_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(file_path), str(failure_path))
        self._restore_targets[failure_path] = file_path
        log(f"Moved failed file to {failure_path}: {file_path}", "warning")
        return True

    def move_files(self, file_paths: Iterable[Path]) -> None:
        for file_path in file_paths:
            self.move_file(file_path)

    def restore_all(self) -> None:
        if not self.root.exists():
            return

        restored = 0
        for failure_path in sorted(self.root.rglob("*")):
            if failure_path.is_file():
                restore_path = self._restore_path(failure_path)
                restore_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(failure_path), str(restore_path))
                restored += 1

        self._remove_empty_dirs()

        if restored:
            log(f"Restored {restored} failed file(s) to memories folder.", "info")

    def _relative_path(self, file_path: Path) -> Path:
        try:
            return file_path.resolve().relative_to(Config.memories_folder.resolve())
        except ValueError:
            return Path(file_path.name)

    def _restore_path(self, failure_path: Path) -> Path:
        remembered_path = self._restore_targets.get(failure_path)
        if remembered_path is not None:
            return self._available_path(remembered_path, "restored")

        relative_path = failure_path.relative_to(self.root)
        return self._available_path(Config.memories_folder / relative_path, "restored")

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

    def _remove_empty_dirs(self) -> None:
        for path in sorted(self.root.rglob("*"), reverse=True):
            if path.is_dir():
                with suppress(OSError):
                    path.rmdir()

        with suppress(OSError):
            self.root.rmdir()
