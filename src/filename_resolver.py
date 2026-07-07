from pathlib import Path


class FileNameResolver:
    def __init__(self, path: Path) -> None:
        self.path = path

    def run(self) -> Path:
        candidate = self.path
        index = 1
        while candidate.exists():
            candidate = self._with_index(index)
            index += 1
        return candidate

    def _with_index(self, index: int) -> Path:
        return self.path.parent / f"{self.path.stem}_{index}{self.path.suffix}"