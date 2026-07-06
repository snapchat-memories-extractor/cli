import json
from pathlib import Path

from src.config import Config
from src.logger import log


class MemoriesRepository:
    def get_raw_items(self) -> list[dict]:
        data = self._load()
        if not data:
            return []

        raw_items = data.get("Saved Media", [])
        return [item for item in raw_items if self._has_usable_location(item)]

    @staticmethod
    def _load() -> dict:
        if not Config.json_path.exists():
            log(f"Memories JSON file not found at {Config.json_path}", "error", "MISS")
            return {}

        with Path.open(Config.json_path, encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def _has_usable_location(item: dict) -> bool:
        location = item.get("Location")
        if not location:
            return False

        coords_part = location.replace("Latitude, Longitude: ", "")
        try:
            latitude, longitude = map(float, coords_part.split(", "))
        except (ValueError, AttributeError):
            return False

        return not (latitude == 0.0 and longitude == 0.0)