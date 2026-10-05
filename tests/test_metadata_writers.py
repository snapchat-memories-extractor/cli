from __future__ import annotations

import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import piexif
import pytest
from PIL import Image

from src.config import Config
from src.metadata.image_metadata_writer import ImageMetadataWriter
from src.metadata.json_memory_loader import Memory
from src.metadata.video_metadata_writer import (
    VIDEO_METADATA_FAILED,
    VideoMetadataWriter,
)


def _memory(
    file_path: Path,
    coords: tuple[float, float] | None = (60.123456, 24.654321),
) -> Memory:
    return Memory(
        captured_at=datetime(
            2024,
            5,
            1,
            12,
            30,
            5,
            tzinfo=timezone(timedelta(hours=2)),
        ),
        location_coords=coords,
        file_path=file_path,
    )


def test_image_metadata_writer_converts_decimal_degrees_to_dms() -> None:
    assert ImageMetadataWriter._decimal_to_dms(-12.5) == (
        (12, 1),
        (30, 1),
        (0, 1_000_000),
    )
    assert ImageMetadataWriter._decimal_to_dms(1.25) == (
        (1, 1),
        (15, 1),
        (0, 1_000_000),
    )


def test_image_metadata_writer_sets_utc_datetime_fields(tmp_path: Path) -> None:
    writer = ImageMetadataWriter(_memory(tmp_path / "photo.jpg"))

    writer._set_datetime_fields()

    expected = b"2024:05:01 10:30:05"
    assert writer.exif_metadata["Exif"][piexif.ExifIFD.DateTimeOriginal] == expected
    assert writer.exif_metadata["Exif"][piexif.ExifIFD.DateTimeDigitized] == expected
    assert writer.exif_metadata["0th"][piexif.ImageIFD.DateTime] == expected


def test_image_metadata_writer_sets_gps_references_for_coordinate_signs(
    tmp_path: Path,
) -> None:
    writer = ImageMetadataWriter(_memory(tmp_path / "photo.jpg", (-12.5, 45.25)))

    writer._set_gps_fields()

    gps = writer.exif_metadata["GPS"]
    assert gps[piexif.GPSIFD.GPSLatitudeRef] == b"S"
    assert gps[piexif.GPSIFD.GPSLongitudeRef] == b"E"
    assert gps[piexif.GPSIFD.GPSLatitude][0] == (12, 1)
    assert gps[piexif.GPSIFD.GPSLongitude][0] == (45, 1)


def test_image_metadata_writer_leaves_gps_empty_without_coordinates(
    tmp_path: Path,
) -> None:
    writer = ImageMetadataWriter(_memory(tmp_path / "photo.jpg", None))

    writer._set_gps_fields()

    assert writer.exif_metadata["GPS"] == {}


def test_image_metadata_writer_runs_against_real_jpeg(tmp_path: Path) -> None:
    Config.cli_options["jpeg_quality"] = 100
    image_path = tmp_path / "photo.jpg"
    Image.new("RGB", (3, 3), (120, 40, 10)).save(image_path, format="JPEG")

    ImageMetadataWriter(_memory(image_path)).run()

    exif = piexif.load(str(image_path))
    assert exif["Exif"][piexif.ExifIFD.DateTimeOriginal] == b"2024:05:01 10:30:05"
    assert exif["GPS"][piexif.GPSIFD.GPSLatitudeRef] == b"N"
    assert exif["GPS"][piexif.GPSIFD.GPSLongitudeRef] == b"E"


def test_video_metadata_writer_formats_iso6709_coordinates() -> None:
    assert VideoMetadataWriter._to_iso6709(60.1, 24.2) == "+60.100000+24.200000/"
    assert VideoMetadataWriter._to_iso6709(-12.5, -45.25) == "-12.500000-45.250000/"


def test_video_metadata_writer_builds_no_metadata_args_without_coordinates(
    tmp_path: Path,
) -> None:
    writer = VideoMetadataWriter(_memory(tmp_path / "clip.mp4", None))

    assert writer._ffmpeg_metadata_arguments() == []


def test_video_metadata_writer_builds_location_metadata_args(tmp_path: Path) -> None:
    writer = VideoMetadataWriter(_memory(tmp_path / "clip.mp4", (60.1, -24.2)))

    assert writer._ffmpeg_metadata_arguments() == [
        "-metadata",
        "location=+60.100000-24.200000/",
        "-metadata",
        "com.apple.quicktime.location.ISO6709=+60.100000-24.200000/",
        "-metadata",
        "Keys:GPSCoordinates=60.1, -24.2",
    ]


def test_video_metadata_writer_builds_copy_command(tmp_path: Path) -> None:
    file_path = tmp_path / "clip.mp4"
    temp_path = tmp_path / "clip.tmp.mp4"
    writer = VideoMetadataWriter(_memory(file_path))

    command = writer._build_ffmpeg_command(temp_path)

    assert command[1:5] == ["-i", str(file_path), "-c", "copy"]
    assert "location=+60.123456+24.654321/" in command
    assert command[-1] == str(temp_path)


def test_video_metadata_writer_replaces_original_on_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "clip.mp4"
    file_path.write_bytes(b"old")
    seen: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        seen["command"] = command
        seen["kwargs"] = kwargs
        Path(command[-1]).write_bytes(b"new")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("src.metadata.video_metadata_writer.subprocess.run", fake_run)

    VideoMetadataWriter(_memory(file_path)).run()

    assert file_path.read_bytes() == b"new"
    assert seen["kwargs"]["timeout"] == Config.cli_options["ffmpeg_timeout"]
    assert seen["kwargs"]["check"] is False
    assert seen["kwargs"]["capture_output"] is True


def test_video_metadata_writer_removes_temp_file_and_raises_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "clip.mp4"
    file_path.write_bytes(b"old")

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        Path(command[-1]).write_bytes(b"partial")
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr("src.metadata.video_metadata_writer.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match=VIDEO_METADATA_FAILED):
        VideoMetadataWriter(_memory(file_path)).run()

    assert file_path.read_bytes() == b"old"
    assert not (tmp_path / "clip.tmp.mp4").exists()


def test_video_metadata_writer_logs_failure_without_temp_file(tmp_path: Path) -> None:
    file_path = tmp_path / "clip.mp4"
    file_path.write_bytes(b"old")
    writer = VideoMetadataWriter(_memory(file_path))

    writer._log_ffmpeg_failure(
        subprocess.CompletedProcess(["ffmpeg"], 1),
        tmp_path / "missing.tmp.mp4",
    )

    assert file_path.read_bytes() == b"old"
