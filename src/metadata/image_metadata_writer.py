from pathlib import Path

import piexif
from PIL import Image

from src.media_dispatcher.image_saver import save_image
from src.memories import Memory


class ImageMetadataWriter:
    def __init__(self, memory: Memory | None, file_path: Path) -> None:
        self.memory = memory
        self.file_path = file_path

        self.exif_metadata = {"0th": {}, "Exif": {}, "GPS": {}}

    def write_image_metadata(self) -> bool:
        if self.memory is None:
            return False

        self._set_datetime_fields()
        self._set_gps_fields()
        self._save_image_with_exif()
        return True

    def _set_datetime_fields(self) -> None:
        datetime_bytes = self.memory.exif_datetime.encode("utf-8")
        exif = self.exif_metadata["Exif"]
        zeroth = self.exif_metadata["0th"]

        exif[piexif.ExifIFD.DateTimeOriginal] = datetime_bytes
        exif[piexif.ExifIFD.DateTimeDigitized] = datetime_bytes
        zeroth[piexif.ImageIFD.DateTime] = datetime_bytes

    def _set_gps_fields(self) -> None:
        coordinates = self.memory.location_coords

        if not coordinates:
            return

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
        save_image(self.file_path, exif_bytes=exif_data_bytes)