import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from src.config import Config
from src.logger import log

Coordinates = tuple[float, float]


class Memory(BaseModel):
    captured_at: datetime
    location_coords: Coordinates
    file_path: Path | None = None


def load_json_memories() -> list[Memory]:
    data = _load_json()
    raw_items = data.get("Saved Media", [])

    memories = []
    for item in raw_items:
        coordinates = _parse_location(item)
        captured_at = _parse_datetime(item)
        if coordinates is not None and captured_at is not None:
            memories.append(
                Memory(captured_at=captured_at, location_coords=coordinates)
            )
        elif coordinates is None:
            _log_missing_location(item)

    return memories


def _load_json() -> dict:
    with Path.open(Config.json_path, encoding="utf-8") as file:
        return json.load(file)


def _log_missing_location(item: dict) -> None:
    message = f"Skipped JSON memory with no usable location: {item.get('Date')}"
    if Config.cli_options["strict_location"]:
        log(message, "error", "LOC")
    else:
        log(message, "debug")


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
