import json
from pathlib import Path

from src.config import Config

Coordinates = tuple[float, float]


def load_located_json_items() -> list[dict]:
    data = _load_json()
    if not data:
        return []

    raw_items = data.get("Saved Media", [])
    located_items = []
    for item in raw_items:
        coordinates = _parse_location_coords(item)
        if coordinates is not None:
            located_items.append({**item, "location_coords": coordinates})

    return located_items


def _load_json() -> dict:
    with Path.open(Config.json_path, encoding="utf-8") as file:
        return json.load(file)


def _parse_location_coords(item: dict) -> Coordinates | None:
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
