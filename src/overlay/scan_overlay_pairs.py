from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from src.helpers import scan_memory_files
from src.logger import log


@dataclass(frozen=True)
class OverlayPair:
    media_id: str
    main_path: Path
    overlay_path: Path


def scan_overlay_pairs() -> list[OverlayPair]:
    grouped = _group_by_id(scan_memory_files())
    return _build_pairs(grouped)


def _group_by_id(files: list[Path]) -> dict[str, dict[str, Path]]:
    grouped: dict[str, dict[str, Path]] = defaultdict(dict)
    for file_path in files:
        parsed = _parse_filename(file_path)
        if parsed is None:
            continue
        media_id, role = parsed
        grouped[media_id][role] = file_path
    return grouped


def _parse_filename(file_path: Path) -> tuple[str, str] | None:
    stem = file_path.stem
    if stem.endswith("-main"):
        return stem[: -len("-main")], "main"
    if stem.endswith("-overlay"):
        return stem[: -len("-overlay")], "overlay"
    return None


def _build_pairs(grouped: dict[str, dict[str, Path]]) -> list[OverlayPair]:
    pairs = []
    for media_id in sorted(grouped.keys()):
        roles = grouped[media_id]
        main_path = roles.get("main")
        overlay_path = roles.get("overlay")

        if main_path and overlay_path:
            pairs.append(OverlayPair(media_id, main_path, overlay_path))
        elif main_path:
            log(
                f"Found main file with no matching overlay for id "
                f"'{media_id}': {main_path}. Skipping.",
                "warning",
            )
        elif overlay_path:
            log(
                f"Found overlay file with no matching main for id "
                f"'{media_id}': {overlay_path}. Skipping.",
                "warning",
            )
    return pairs
