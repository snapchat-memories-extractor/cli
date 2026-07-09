from datetime import datetime, timezone

from pydantic import BaseModel, Field, model_validator


class Memory(BaseModel):
    date: str = Field(alias="Date")
    media_type: str = Field(alias="Media Type")
    location: str | None = Field(default=None, alias="Location")

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

    @property
    def location_coords(self) -> tuple[float, float] | None:
        if not self.location:
            return None

        location_coords = self.location.replace("Latitude, Longitude: ", "")
        latitude, longitude = map(float, location_coords.split(", "))

        if latitude == 0.0 and longitude == 0.0:
            return None

        return (latitude, longitude)