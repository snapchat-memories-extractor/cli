from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

import src.core.state_store.state_store as state_store_module
from src.config import Config
from src.logger.log import APP_LOGGER_NAME

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def cli_options() -> dict[str, object]:
    return {
        "memories_json": None,
        "memories_folder": None,
        "output": None,
        "logs_path": None,
        "reset_state": False,
        "retry_failed": False,
        "overlay_mode": "on",
        "overlay_applier_concurrency": 2,
        "overlay_video_crf": 18,
        "overlay_video_preset": "fast",
        "overlay_video_pixel_format": "yuv420p",
        "gps_writer_concurrency": 2,
        "jxl_converter_concurrency": 2,
        "av1_converter_concurrency": 2,
        "write_metadata": True,
        "strict_location": False,
        "jpeg_quality": 95,
        "logs_amount": 5,
        "convert_to_jxl": False,
        "jxl_effort": 9,
        "log_level": logging.DEBUG,
        "ffmpeg_timeout": 60,
        "video_codec": "h264",
        "av1_cpu_used": 4,
        "av1_tile_columns": 0,
        "av1_tile_rows": 0,
        "av1_row_mt": 1,
        "av1_aq_mode": 0,
        "av1_lag_in_frames": 25,
        "av1_tune": None,
        "av1_usage": "good",
        "film_grain": 0,
        "grain_denoise": 1,
        "av1_crf": 36,
        "ffmpeg_pixel_format": "yuv420p",
        "jxl_timeout": 120,
        "ffmpeg_preset": "fast",
    }


@pytest.fixture(autouse=True)
def isolated_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    cli_options: dict[str, object],
) -> Iterator[None]:
    monkeypatch.setattr(Config, "cli_options", dict(cli_options))
    monkeypatch.setattr(Config, "json_path", tmp_path / "memories_history.json")
    monkeypatch.setattr(Config, "memories_folder", tmp_path / "memories")
    monkeypatch.setattr(Config, "output_folder", tmp_path / "output")
    monkeypatch.setattr(Config, "logs_folder", tmp_path / "logs")

    logger = logging.getLogger(APP_LOGGER_NAME)
    original_handlers = list(logger.handlers)
    original_level = logger.level
    original_propagate = logger.propagate

    for handler in original_handlers:
        logger.removeHandler(handler)

    logger.setLevel(logging.DEBUG)
    logger.propagate = True

    yield

    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    for handler in original_handlers:
        logger.addHandler(handler)

    logger.setLevel(original_level)
    logger.propagate = original_propagate


@pytest.fixture
def state_path(tmp_path: Path) -> Path:
    return tmp_path / "pipeline-state.json"


@pytest.fixture
def state_store(monkeypatch: pytest.MonkeyPatch, state_path: Path):
    monkeypatch.setattr(
        state_store_module,
        "default_state_path",
        lambda: state_path,
    )
    return state_store_module.StateStore()
