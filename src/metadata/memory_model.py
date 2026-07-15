from datetime import datetime, timezone

from pydantic import BaseModel, Field, model_validator


class Memory(BaseModel):
    date: str = Field(alias="Date")
    media_type: str = Field(alias="Media Type")
    location_coords: tuple[float, float]

    exif_datetime: str = ""
    video_creation_time: str = ""

    @model_validator(mode="after")
    def parse_datetime(self) -> "Memory":
        datetime_object = datetime.strptime(
            self.date, "%Y-%m-%d %H:%M:%S UTC"
        ).replace(tzinfo=timezone.utc)
        self.exif_datetime = datetime_object.strftime("%Y:%m:%d %H:%M:%S")
        self.video_creation_time = datetime_object.strftime("%Y-%m-%dT%H:%M:%S")
        return self
