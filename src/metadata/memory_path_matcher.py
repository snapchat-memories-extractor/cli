from collections import defaultdict
from datetime import date
from pathlib import Path

from src.logger import log
from src.metadata.json_memory_loader import Memory


def match_memory_paths(
    media_files: list[Path],
    memories: list[Memory],
) -> tuple[list[Memory], list[Path]]:
    memories_by_date = _group_memories_by_date(memories)
    media_files_by_date, unmatched_files = _group_media_files_by_date(media_files)
    matched_memories = []

    for media_date, day_files in sorted(media_files_by_date.items()):
        day_memories = memories_by_date.get(media_date, [])

        if len(day_files) != len(day_memories):
            _log_date_count_mismatch(media_date, day_files, day_memories)
            unmatched_files.extend(day_files)
            continue

        sorted_files = _sort_media_files(day_files)
        if sorted_files is None:
            unmatched_files.extend(day_files)
            continue

        sorted_memories = sorted(day_memories, key=lambda memory: memory.captured_at)
        for file_path, memory in zip(sorted_files, sorted_memories, strict=True):
            memory.file_path = file_path
            matched_memories.append(memory)

    return matched_memories, unmatched_files


def _group_memories_by_date(memories: list[Memory]) -> dict[date, list[Memory]]:
    grouped = defaultdict(list)
    for memory in memories:
        grouped[memory.captured_at.date()].append(memory)
    return grouped


def _group_media_files_by_date(
    media_files: list[Path],
) -> tuple[dict[date, list[Path]], list[Path]]:
    grouped = defaultdict(list)
    unmatched_files = []

    for file_path in media_files:
        media_date = _parse_filename_date(file_path)
        if media_date is None:
            log(
                f"Could not match media file to JSON memory by filename date: "
                f"{file_path}",
                "error",
                "MATCH",
            )
            unmatched_files.append(file_path)
            continue

        grouped[media_date].append(file_path)

    return grouped, unmatched_files


def _parse_filename_date(file_path: Path) -> date | None:
    try:
        return date.fromisoformat(file_path.name[:10])
    except ValueError:
        return None


def _sort_media_files(media_files: list[Path]) -> list[Path] | None:
    try:
        return sorted(media_files, key=lambda file_path: file_path.stat().st_mtime)
    except OSError as error:
        log(
            f"Could not sort media files by modified time: {error}",
            "error",
            "MATCH",
        )
        return None


def _log_date_count_mismatch(
    media_date: date,
    media_files: list[Path],
    memories: list[Memory],
) -> None:
    log(
        f"Could not match media files to JSON memories for {media_date}: "
        f"{len(media_files)} file(s), {len(memories)} JSON memory item(s). "
        "Skipping this date.",
        "error",
        "MATCH",
    )
