from collections import defaultdict
from pathlib import Path

from src.logger import log


class MediaPair:
    def __init__(
        self,
        media_id: str,
        main_path: Path,
        overlay_path: Path,
    ) -> None:
        self.media_id = media_id
        self.main_path = main_path
        self.overlay_path = overlay_path


class FolderScanner:
    def __init__(self, folder: Path, ignored_folder: Path | None = None) -> None:
        self.folder = folder
        self.ignored_folder = ignored_folder

    def scan_overlay_pairs(self) -> list[MediaPair]:
        grouped = self._group_by_id(self.scan_media_files())
        return self._build_pairs(grouped)

    def scan_media_files(self) -> list[Path]:
        return sorted(
            path
            for path in self.folder.rglob("*")
            if path.is_file() and not self._is_ignored(path)
        )

    def _is_ignored(self, path: Path) -> bool:
        if self.ignored_folder is None:
            return False

        return self.ignored_folder in path.parents

    def _group_by_id(self, files: list[Path]) -> dict[str, dict[str, Path]]:
        grouped: dict[str, dict[str, Path]] = defaultdict(dict)
        for file_path in files:
            parsed = self._parse_filename(file_path)
            if parsed is None:
                continue
            media_id, role = parsed
            grouped[media_id][role] = file_path
        return grouped

    @staticmethod
    def _parse_filename(file_path: Path) -> tuple[str, str] | None:
        stem = file_path.stem
        if stem.endswith("-main"):
            return stem[: -len("-main")], "main"
        if stem.endswith("-overlay"):
            return stem[: -len("-overlay")], "overlay"
        return None

    @staticmethod
    def _build_pairs(grouped: dict[str, dict[str, Path]]) -> list[MediaPair]:
        pairs = []
        for media_id in sorted(grouped.keys()):
            roles = grouped[media_id]
            main_path = roles.get("main")
            overlay_path = roles.get("overlay")

            if main_path and overlay_path:
                pairs.append(MediaPair(media_id, main_path, overlay_path))
            elif overlay_path:
                log(
                    f"Found overlay file with no matching main for id "
                    f"'{media_id}': {overlay_path}. Skipping.",
                    "warning",
                )
        return pairs
