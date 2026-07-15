from datetime import datetime
from pathlib import Path

from pydantic import BaseModel


class Memory(BaseModel):
    captured_at: datetime
    location_coords: tuple[float, float]
    file_path: Path | None = None
