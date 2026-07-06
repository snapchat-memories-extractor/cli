from collections import defaultdict
from pathlib import Path

from src.logger import log


class MediaPair:
    def __init__(
        self,
        media_id: str,
        main_path: Path | None = None,
        overlay_path: Path | None = None,
    ) -> None:
        self.media_id = media_id
        self.main_path = main_path
        self.overlay_path = overlay_path


class FolderScanner:
    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def run(self) -> list[MediaPair]:
        grouped = self._group_by_id(self._scan_files())
        return self._build_pairs(grouped)

    def _scan_files(self) -> list[Path]:
        return sorted(p for p in self.folder.rglob("*") if p.is_file())

    def _group_by_id(self, files: list[Path]) -> dict[str, dict[str, Path]]:
        grouped: dict[str, dict[str, Path]] = defaultdict(dict)
        for file_path in files:
            media_id, role = self._parse_filename(file_path)
            if media_id is None:
                continue
            grouped[media_id][role] = file_path
        return grouped

    @staticmethod
    def _parse_filename(file_path: Path) -> tuple[str | None, str | None]:
        stem = file_path.stem
        if stem.endswith("-main"):
            return stem[: -len("-main")], "main"
        if stem.endswith("-overlay"):
            return stem[: -len("-overlay")], "overlay"
        return None, None

    @staticmethod
    def _build_pairs(grouped: dict[str, dict[str, Path]]) -> list[MediaPair]:
        pairs = []
        for media_id in sorted(grouped.keys()):
            roles = grouped[media_id]
            main_path = roles.get("main")
            overlay_path = roles.get("overlay")

            if overlay_path and not main_path:
                log(
                    f"Found overlay file with no matching main for id "
                    f"'{media_id}': {overlay_path}. Skipping.",
                    "warning",
                )
                continue

            pairs.append(MediaPair(media_id, main_path, overlay_path))
        return pairs