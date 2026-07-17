from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from src.config import Config
from src.metadata.json_memory_loader import Memory
from src.metadata.media_datetime_reader import MediaDatetimeReader


def match_memory_paths(
    media_files: list[Path],
    memories: list[Memory],
) -> tuple[list[Memory], list[Path]]:
    lookup = _build_memory_lookup(memories)
    captured_at_by_file = _read_media_datetimes(media_files)
    matched_memories = []
    unmatched_files = []

    for file_path in media_files:
        captured_at = captured_at_by_file[file_path]
        memory = _take_matching_memory(captured_at, lookup)

        if memory is None:
            unmatched_files.append(file_path)
            continue

        memory.file_path = file_path
        matched_memories.append(memory)

    return matched_memories, unmatched_files


def _build_memory_lookup(memories: list[Memory]) -> dict[datetime, list[Memory]]:
    lookup: dict[datetime, list[Memory]] = {}
    for memory in memories:
        lookup.setdefault(memory.captured_at, []).append(memory)
    return lookup


def _read_media_datetimes(
    media_files: list[Path],
) -> dict[Path, datetime | None]:
    max_workers = Config.cli_options["gps_reader_concurrency"]
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        captured_at_values = executor.map(
            lambda file_path: MediaDatetimeReader(file_path).run(),
            media_files,
        )
        return dict(zip(media_files, captured_at_values, strict=True))


def _take_matching_memory(
    captured_at: datetime | None,
    lookup: dict[datetime, list[Memory]],
) -> Memory | None:
    if captured_at is None:
        return None

    candidates = lookup.get(captured_at)
    if not candidates:
        return None

    memory = candidates.pop(0)
    if not candidates:
        del lookup[captured_at]

    return memory
