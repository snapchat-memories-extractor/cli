from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.metadata.image_metadata_writer import ImageMetadataWriter
from src.metadata.video_metadata_writer import VideoMetadataWriter


@pytest.fixture
def mock_memory_image() -> MagicMock:
    memory = MagicMock()
    memory.exif_datetime = "2023:12:05 12:34:56"
    memory.location_coords = (37.0, -122.0)
    return memory


@pytest.fixture
def mock_memory_video() -> MagicMock:
    memory = MagicMock()
    memory.video_creation_time = "2023-12-05T12:34:56"
    memory.location_coords = (37.0, -122.0)
    return memory


def test_write_image_metadata(mock_memory_image: MagicMock, mocker) -> None:
    mock_img = MagicMock()
    mock_open = mocker.patch("PIL.Image.open")
    mock_open.return_value.__enter__.return_value = mock_img
    mock_dump = mocker.patch("piexif.dump", return_value=b"exifbytes")
    writer = ImageMetadataWriter(mock_memory_image, Path("dummy.jpg"))
    # Call the actual _save_image_with_exif to trigger piexif.dump
    writer._save_image_with_exif()
    assert mock_dump.called


def test_write_video_metadata(mock_memory_video: MagicMock, mocker) -> None:
    # Patch where get_ffmpeg_exe is actually used (in your video_metadata_writer module)
    mocker.patch(
        "src.metadata.video_metadata_writer.get_ffmpeg_exe", return_value="ffmpeg"
    )
    mocker.patch.object(Path, "replace", return_value=None)

    mock_run = mocker.patch("subprocess.run")
    mock_run.return_value.returncode = 0

    writer = VideoMetadataWriter(mock_memory_video, Path("dummy.mp4"))
    writer._log_ffmpeg_failure = MagicMock()
    writer.run()

    assert mock_run.called
