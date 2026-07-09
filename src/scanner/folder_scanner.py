from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from src.logger import log


@dataclass(frozen=True)
class MediaPair:
    media_id: str
    main_path: Path
    overlay_path: Path


class FolderScanner:
    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def scan_overlay_pairs(self) -> list[MediaPair]:
        grouped = self._group_by_id(self.scan_media_files())
        return self._build_pairs(grouped)

    def scan_media_files(self) -> list[Path]:
        return sorted(
            path
            for path in self.folder.iterdir()
            if path.is_file()
        )

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
