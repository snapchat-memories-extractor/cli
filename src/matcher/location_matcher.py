import threading
from datetime import datetime, timezone

from src.logger import log
from src.memories import Memory


class LocationMatcher:
    def __init__(self, memories: list[Memory]) -> None:
        self._lookup = self._build_lookup(memories)
        self._lock = threading.Lock()

    @staticmethod
    def _build_lookup(memories: list[Memory]) -> dict[datetime, list[Memory]]:
        lookup: dict[datetime, list[Memory]] = {}
        for memory in memories:
            key = LocationMatcher._memory_datetime(memory)
            lookup.setdefault(key, []).append(memory)
        return lookup

    @staticmethod
    def _memory_datetime(memory: Memory) -> datetime:
        return datetime.strptime(
            memory.video_creation_time, "%Y-%m-%dT%H:%M:%S"
        ).replace(tzinfo=timezone.utc)

    def match_one(self, media_id: str, captured_at: datetime | None) -> Memory | None:
        if captured_at is None:
            return None

        with self._lock:
            candidates = self._lookup.get(captured_at)
            if not candidates:
                return None

            if len(candidates) > 1:
                # Two json entries share the same second, never guess which one belongs to this file.
                log(
                    f"Ambiguous match for '{media_id}': {len(candidates)} json "
                    "entries share the same capture datetime. Skipping match.",
                    "error",
                    "MATCH",
                )
                return None

            memory = candidates[0]
            del self._lookup[captured_at]
            return memory