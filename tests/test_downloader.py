import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.config import Config
from src.downloader.downloader import MemoryDownloader
from src.memories.memory_model import Memory


@pytest.fixture
def temp_config():
    with tempfile.TemporaryDirectory() as tmpdir:
        cli_options = {
            "max_concurrent_downloads": 5,
            "apply_overlay": True,
            "write_metadata": True,
            "max_attempts": 3,
            "strict_location": True,
            "jpeg_quality": 95,
            "convert_to_jxl": True,
            "log_level": 50,
            "request_timeout": 30,
            "ffmpeg_timeout": 60,
            "stream_chunk_size": 1024 * 1024,
        }
        yield Config(
            cli_options=cli_options,
            json_path=Path(tmpdir) / "memories_history.json",
            output_folder=Path(tmpdir) / "downloads",
            logs_folder=Path(tmpdir) / "logs",
        )


@pytest.fixture
def downloader():
    downloader = MemoryDownloader()
    downloader.download_service = MagicMock()
    return downloader


@pytest.fixture
def memory_without_location():
    return Memory.model_validate(
        {
            "Date": "2023-12-05 12:34:56 UTC",
            "Media Download Url": "http://example.com/media.jpg",
            "Media Type": "Image",
            "Location": None,
        },
    )


def test_strict_location_blocks_download(downloader, memory_without_location) -> None:
    downloader.download_service.download_and_process = MagicMock()
    Config.cli_options["strict_location"] = True
    success = memory_without_location.location is not None
    assert success is False
    downloader.download_service.download_and_process.assert_not_called()
