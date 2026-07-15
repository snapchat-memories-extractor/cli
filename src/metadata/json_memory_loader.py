import json
from datetime import datetime, timezone
from pathlib import Path

from src.config import Config
from src.metadata.memory_model import Memory

Coordinates = tuple[float, float]


def load_json_memories() -> list[Memory]:
    data = _load_json()
    raw_items = data.get("Saved Media", [])

    memories = []
    for item in raw_items:
        coordinates = _parse_location(item)
        datetime = _parse_datetime(item)
        if coordinates is not None and datetime is not None:
            memories.append(
                Memory(captured_at=datetime, location_coords=coordinates)
            )

    return memories


def _load_json() -> dict:
    with Path.open(Config.json_path, encoding="utf-8") as file:
        return json.load(file)


def _parse_location(item: dict) -> Coordinates | None:
    location = item.get("Location")
    if not location:
        return None

    coords_part = location.replace("Latitude, Longitude: ", "")
    try:
        latitude, longitude = map(float, coords_part.split(", "))
    except (ValueError, AttributeError):
        return None

    if latitude == 0.0 and longitude == 0.0:
        return None

    return (latitude, longitude)


def _parse_datetime(item: dict) -> datetime | None:
    raw_date = item.get("Date")
    if not isinstance(raw_date, str):
        return None

    timestamp = raw_date.removesuffix(" UTC")

    try:
        return datetime.fromisoformat(timestamp).replace(
            tzinfo=timezone.utc,
            microsecond=0,
        )
    except ValueError:
        return None
