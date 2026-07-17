from datetime import timezone

import piexif
from PIL import Image

from src.config import Config
from src.metadata.json_memory_loader import Memory


class ImageMetadataWriter:
    def __init__(self, memory: Memory) -> None:
        self.memory = memory
        self.file_path = memory.file_path

        self.exif_metadata = {"0th": {}, "Exif": {}, "GPS": {}}

    def run(self) -> None:
        self._set_datetime_fields()
        self._set_gps_fields()
        self._save_image_with_exif()

    def _set_datetime_fields(self) -> None:
        captured_at = self.memory.captured_at.astimezone(timezone.utc)
        datetime_bytes = captured_at.strftime("%Y:%m:%d %H:%M:%S").encode("ascii")
        exif = self.exif_metadata["Exif"]
        zeroth = self.exif_metadata["0th"]

        exif[piexif.ExifIFD.DateTimeOriginal] = datetime_bytes
        exif[piexif.ExifIFD.DateTimeDigitized] = datetime_bytes
        zeroth[piexif.ImageIFD.DateTime] = datetime_bytes

    def _set_gps_fields(self) -> None:
        latitude, longitude = self.memory.location_coords
        gps = self.exif_metadata["GPS"]
        latitude_dms = self._decimal_to_dms(latitude)
        longitude_dms = self._decimal_to_dms(longitude)

        lat_ref = b"N" if latitude >= 0 else b"S"
        lon_ref = b"E" if longitude >= 0 else b"W"

        gps[piexif.GPSIFD.GPSLatitude] = latitude_dms
        gps[piexif.GPSIFD.GPSLatitudeRef] = lat_ref
        gps[piexif.GPSIFD.GPSLongitude] = longitude_dms
        gps[piexif.GPSIFD.GPSLongitudeRef] = lon_ref

    @staticmethod
    def _decimal_to_dms(
        decimal_degrees: float,
    ) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
        absolute_value = abs(decimal_degrees)

        degrees = int(absolute_value)
        degrees_fraction = absolute_value - degrees

        minutes_decimal = degrees_fraction * 60
        minutes = int(minutes_decimal)
        minutes_fraction = minutes_decimal - minutes

        seconds_decimal = minutes_fraction * 60
        seconds_numerator = int(seconds_decimal * 1000000)
        seconds_denominator = 1000000

        return (
            (degrees, 1),
            (minutes, 1),
            (seconds_numerator, seconds_denominator),
        )

    def _save_image_with_exif(self) -> None:
        exif_data_bytes = piexif.dump(self.exif_metadata)
        quality = Config.cli_options["jpeg_quality"]

        with Image.open(self.file_path) as image:
            image.save(str(self.file_path), quality, exif_data_bytes)
