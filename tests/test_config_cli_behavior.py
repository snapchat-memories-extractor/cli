from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pytest

from src.config import Config, build_cli_options, parse_log_level
from src.config.cli_args import _parse_positive_int, get_cli_args


def _make_args(**overrides: object) -> argparse.Namespace:
    values = {
        "memories_json": None,
        "memories_folder": None,
        "output": None,
        "logs_path": None,
        "reset_state": False,
        "retry_failed": False,
        "overlay_mode": "on",
        "overlay_applier_concurrency": 10,
        "overlay_video_crf": 18,
        "overlay_video_preset": "fast",
        "overlay_video_pixel_format": "yuv420p",
        "metadata_writer_concurrency": 10,
        "jxl_converter_concurrency": 10,
        "av1_converter_concurrency": 10,
        "no_metadata": False,
        "keep_conversion_originals": False,
        "strict_location": False,
        "jpeg_quality": 95,
        "logs_amount": 5,
        "jxl": False,
        "jxl_effort": 9,
        "log_level": logging.CRITICAL + 10,
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
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_parse_log_level_accepts_numeric_and_named_values() -> None:
    assert parse_log_level("0") == logging.CRITICAL + 10
    assert parse_log_level("OFF") == logging.CRITICAL + 10
    assert parse_log_level("critical") == logging.CRITICAL
    assert parse_log_level("4") == logging.INFO
    assert parse_log_level("debug") == logging.DEBUG


def test_parse_log_level_rejects_unknown_values() -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="Invalid log level"):
        parse_log_level("verbose")


@pytest.mark.parametrize("value", ["1", "12"])
def test_parse_positive_int_accepts_values_above_zero(value: str) -> None:
    assert _parse_positive_int(value) == int(value)


@pytest.mark.parametrize("value", ["0", "-1", "not-a-number"])
def test_parse_positive_int_rejects_invalid_values(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError, match="positive integer"):
        _parse_positive_int(value)


def test_get_cli_args_uses_current_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["snap-export"])

    args = get_cli_args()

    assert args.memories_json is None
    assert args.memories_folder is None
    assert args.output is None
    assert args.overlay_mode == "on"
    assert args.overlay_applier_concurrency == 10
    assert args.metadata_writer_concurrency == 10
    assert args.no_metadata is False
    assert args.keep_conversion_originals is False
    assert args.log_level == logging.CRITICAL + 10
    assert args.video_codec == "h264"


def test_get_cli_args_accepts_new_and_legacy_video_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "snap-export",
            "--overlay-mode",
            "both",
            "--ffmpeg-preset",
            "slow",
            "--no-metadata",
            "--jxl",
            "--video-codec",
            "av1",
            "--crf",
            "41",
            "--keep-originals",
            "--log-level",
            "DEBUG",
        ],
    )

    args = get_cli_args()

    assert args.overlay_mode == "both"
    assert args.overlay_video_preset == "slow"
    assert args.no_metadata is True
    assert args.jxl is True
    assert args.video_codec == "av1"
    assert args.av1_crf == 41
    assert args.keep_conversion_originals is True
    assert args.log_level == logging.DEBUG


def test_get_cli_args_accepts_new_and_legacy_metadata_concurrency_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["snap-export", "--metadata-writer-concurrency", "8"],
    )

    assert get_cli_args().metadata_writer_concurrency == 8

    monkeypatch.setattr(sys, "argv", ["snap-export", "-gwc", "6"])

    assert get_cli_args().metadata_writer_concurrency == 6


def test_get_cli_args_accepts_ffmpeg_timeout_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "argv", ["snap-export", "--ffmpeg-timeout", "90"])

    assert get_cli_args().ffmpeg_timeout == 90

    monkeypatch.setattr(sys, "argv", ["snap-export", "-ft", "120"])

    assert get_cli_args().ffmpeg_timeout == 120


def test_build_cli_options_maps_public_options_and_inverted_flags() -> None:
    args = _make_args(
        memories_json="memories.json",
        memories_folder="memories",
        output="out",
        logs_path="logs",
        no_metadata=True,
        keep_conversion_originals=True,
        strict_location=True,
        overlay_video_preset="medium",
        jxl=True,
        video_codec="av1",
    )

    options = build_cli_options(args)

    assert options["memories_json"] == "memories.json"
    assert options["memories_folder"] == "memories"
    assert options["output"] == "out"
    assert options["logs_path"] == "logs"
    assert options["write_metadata"] is False
    assert options["keep_conversion_originals"] is True
    assert options["strict_location"] is True
    assert options["convert_to_jxl"] is True
    assert options["video_codec"] == "av1"
    assert options["ffmpeg_preset"] == "medium"


def test_build_cli_options_preserves_concurrency_and_quality_values() -> None:
    args = _make_args(
        overlay_applier_concurrency=7,
        metadata_writer_concurrency=8,
        jxl_converter_concurrency=9,
        av1_converter_concurrency=6,
        jpeg_quality=87,
        jxl_effort=4,
        ffmpeg_timeout=99,
        jxl_timeout=121,
    )

    options = build_cli_options(args)

    assert options["overlay_applier_concurrency"] == 7
    assert options["metadata_writer_concurrency"] == 8
    assert options["jxl_converter_concurrency"] == 9
    assert options["av1_converter_concurrency"] == 6
    assert options["jpeg_quality"] == 87
    assert options["jxl_effort"] == 4
    assert options["ffmpeg_timeout"] == 99
    assert options["jxl_timeout"] == 121


def test_config_path_helpers_use_cli_overrides(tmp_path: Path) -> None:
    json_path = tmp_path / "custom.json"
    memories = tmp_path / "memories-custom"
    output = tmp_path / "output-custom"
    logs = tmp_path / "logs-custom"
    Config.cli_options.update(
        {
            "memories_json": str(json_path),
            "memories_folder": str(memories),
            "output": str(output),
            "logs_path": str(logs),
        }
    )

    assert Config._get_memories_json_path() == json_path
    assert Config._get_memories_folder() == memories
    assert Config._get_output_folder() == output
    assert Config._get_logs_folder() == logs


def test_config_path_helpers_default_to_project_folders() -> None:
    project_root = Path(__file__).resolve().parents[1]

    assert Config._get_memories_json_path() == (
        project_root / "data/memories_history.json"
    )
    assert Config._get_memories_folder() == project_root / "data/memories"
    assert Config._get_output_folder() == project_root / "output"
    assert Config._get_logs_folder() == project_root / "logs"


def test_initialize_config_loads_cli_options_and_resolves_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    args = object()
    options = {
        "memories_json": str(tmp_path / "memories.json"),
        "memories_folder": str(tmp_path / "memories"),
        "output": str(tmp_path / "output"),
        "logs_path": str(tmp_path / "logs"),
    }
    monkeypatch.setattr("src.config.main.get_cli_args", lambda: args)
    monkeypatch.setattr(
        "src.config.main.build_cli_options",
        lambda received_args: options if received_args is args else {},
    )

    Config.initialize_config()

    assert Config.cli_options == options
    assert Config.json_path == tmp_path / "memories.json"
    assert Config.memories_folder == tmp_path / "memories"
    assert Config.output_folder == tmp_path / "output"
    assert Config.logs_folder == tmp_path / "logs"
