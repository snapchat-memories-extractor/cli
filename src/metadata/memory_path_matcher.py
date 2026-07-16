from datetime import datetime
from pathlib import Path

from src.metadata.media_datetime_reader import MediaDatetimeReader
from src.metadata.memory_model import Memory


def match_memory_paths(
    media_files: list[Path],
    memories: list[Memory],
) -> tuple[list[Memory], list[Path]]:
    lookup = _build_memory_lookup(memories)
    matched_memories = []
    unmatched_files = []

    for file_path in media_files:
        captured_at = MediaDatetimeReader(file_path).run()
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
