from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class Memory(BaseModel):
    captured_at: datetime = Field(alias="Date")
    location_coords: tuple[float, float]
    file_path: Path | None = None

    @field_validator("captured_at", mode="before")
    @classmethod
    def parse_captured_at(cls, value: object) -> object:
        if isinstance(value, str):
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S UTC").replace(
                tzinfo=timezone.utc
            )
        if isinstance(value, datetime) and value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(microsecond=0)
        if isinstance(value, datetime):
            return value.replace(tzinfo=timezone.utc, microsecond=0)
        return value
