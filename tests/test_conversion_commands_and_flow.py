from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from src.config import Config, FFmpegConfig
from src.conversion.conversion_concurrency import (
    ConversionSlots,
    conversion_worker_capacity,
)
from src.conversion.conversion_phase import ConversionPhase
from src.conversion.ffmpeg_converter import VideoConverter

if TYPE_CHECKING:
    from src.core.state_store import StateStore


def test_ffmpeg_config_selects_h264_by_default_and_av1_when_requested() -> None:
    assert FFmpegConfig.get_video_codec() == "libx264"

    Config.cli_options["video_codec"] = "av1"

    assert FFmpegConfig.get_video_codec() == "libaom-av1"


def test_ffmpeg_config_builds_av1_speed_quality_and_film_grain_params() -> None:
    Config.cli_options.update(
        {
            "av1_cpu_used": 6,
            "av1_tile_columns": 2,
            "av1_tile_rows": 1,
            "av1_row_mt": 0,
            "av1_aq_mode": 3,
            "av1_lag_in_frames": 12,
            "av1_tune": "psnr",
            "av1_usage": "good",
            "film_grain": 14,
            "grain_denoise": 0,
        }
    )

    assert FFmpegConfig.get_av1_speed_params() == [
        "-cpu-used",
        "6",
        "-tile-columns",
        "2",
        "-tile-rows",
        "1",
        "-row-mt",
        "0",
    ]
    assert FFmpegConfig.get_av1_quality_params() == [
        "-aq-mode",
        "3",
        "-lag-in-frames",
        "12",
        "-usage",
        "good",
        "-tune",
        "psnr",
    ]
    assert FFmpegConfig.get_av1_film_grain_params() == [
        "-denoise-noise-level",
        "14",
        "-aom-params",
        "enable-dnl-denoising=0",
    ]


def test_conversion_worker_capacity_is_at_least_one_and_sums_enabled_work() -> None:
    assert conversion_worker_capacity() == 1

    Config.cli_options.update(
        {
            "convert_to_jxl": True,
            "jxl_converter_concurrency": 3,
            "video_codec": "av1",
            "av1_converter_concurrency": 4,
        }
    )

    assert conversion_worker_capacity() == 7


def test_conversion_slots_use_configured_semaphore_limits() -> None:
    Config.cli_options["jxl_converter_concurrency"] = 2
    Config.cli_options["av1_converter_concurrency"] = 1

    slots = ConversionSlots.from_options()

    assert slots.jxl.acquire(blocking=False)
    assert slots.jxl.acquire(blocking=False)
    assert not slots.jxl.acquire(blocking=False)
    assert slots.av1.acquire(blocking=False)
    assert not slots.av1.acquire(blocking=False)


def test_video_converter_builds_ffmpeg_conversion_command(tmp_path: Path) -> None:
    Config.cli_options.update(
        {
            "video_codec": "av1",
            "av1_crf": 33,
            "ffmpeg_pixel_format": "yuv444p",
            "av1_tune": "ssim",
            "film_grain": 10,
        }
    )
    file_path = tmp_path / "clip.mp4"
    temp_path = tmp_path / "clip.tmp.mp4"

    command = VideoConverter(file_path)._build_ffmpeg_command(temp_path)

    assert command[1:8] == [
        "-y",
        "-i",
        str(file_path),
        "-map_metadata",
        "0",
        "-c:a",
        "copy",
    ]
    assert command[8:14] == ["-c:v", "libaom-av1", "-crf", "33", "-b:v", "0"]
    assert "-tune" in command
    assert "ssim" in command
    assert "-denoise-noise-level" in command
    assert command[-3:] == ["-pix_fmt", "yuv444p", str(temp_path)]


def test_video_converter_replaces_file_on_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "clip.mp4"
    file_path.write_bytes(b"old")
    seen: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        seen["kwargs"] = kwargs
        Path(command[-1]).write_bytes(b"new")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("src.conversion.ffmpeg_converter.subprocess.run", fake_run)

    result = VideoConverter(file_path).run()

    assert result == file_path
    assert file_path.read_bytes() == b"new"
    assert seen["kwargs"]["check"] is True
    assert seen["kwargs"]["timeout"] == Config.cli_options["ffmpeg_timeout"]


def test_video_converter_removes_temp_file_and_raises_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "clip.mp4"
    file_path.write_bytes(b"old")

    def fake_run(command: list[str], **_kwargs: object) -> None:
        Path(command[-1]).write_bytes(b"partial")
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr("src.conversion.ffmpeg_converter.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="ffmpeg exited with code 1") as error:
        VideoConverter(file_path).run()

    assert "Command" not in str(error.value)
    assert file_path.read_bytes() == b"old"
    assert not (tmp_path / "clip.tmp.mp4").exists()


def test_video_converter_shortens_timeout_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "clip.mp4"
    file_path.write_bytes(b"old")

    def fake_run(command: list[str], **_kwargs: object) -> None:
        Path(command[-1]).write_bytes(b"partial")
        raise subprocess.TimeoutExpired(command, timeout=60)

    monkeypatch.setattr("src.conversion.ffmpeg_converter.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="ffmpeg timed out after 60 seconds") as error:
        VideoConverter(file_path).run()

    assert "Command" not in str(error.value)
    assert file_path.read_bytes() == b"old"
    assert not (tmp_path / "clip.tmp.mp4").exists()


def test_conversion_phase_skips_unsupported_media(
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    notes = tmp_path / "notes.txt"

    ConversionPhase(state_store)._process_media(notes)

    assert state_store.get_status(notes, "conversion") == "skipped"


def test_conversion_phase_skips_image_when_jxl_is_disabled(
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    image = tmp_path / "photo.jpg"

    ConversionPhase(state_store)._process_image(image)

    assert state_store.get_status(image, "conversion") == "skipped"


def test_conversion_phase_marks_jxl_success_and_copies_terminal_state(
    monkeypatch: pytest.MonkeyPatch,
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    Config.cli_options["convert_to_jxl"] = True
    image = tmp_path / "photo.jpg"
    jxl = tmp_path / "photo.jxl"
    state_store.mark_done(image, "overlay")
    state_store.mark_skipped(image, "metadata")

    class FakeJXLConverter:
        def __init__(self, input_path: Path) -> None:
            assert input_path == image

        def run(self) -> Path:
            jxl.write_bytes(b"jxl")
            return jxl

    monkeypatch.setattr(
        "src.conversion.conversion_phase.JXLConverter",
        FakeJXLConverter,
    )

    ConversionPhase(state_store)._process_image(image)

    assert state_store.get_status(image, "conversion") == "done"
    assert state_store.get_status(jxl, "conversion") == "done"
    assert state_store.get_status(jxl, "overlay") == "done"
    assert state_store.get_status(jxl, "metadata") == "skipped"


def test_conversion_phase_marks_jxl_failure(
    monkeypatch: pytest.MonkeyPatch,
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    Config.cli_options["convert_to_jxl"] = True
    image = tmp_path / "photo.jpg"

    class FakeJXLConverter:
        def __init__(self, _input_path: Path) -> None:
            pass

        def run(self) -> None:
            return None

    monkeypatch.setattr(
        "src.conversion.conversion_phase.JXLConverter",
        FakeJXLConverter,
    )

    ConversionPhase(state_store)._process_image(image)

    assert state_store.get_status(image, "conversion") == "failed"


def test_conversion_phase_processes_av1_video_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    Config.cli_options["video_codec"] = "av1"
    video = tmp_path / "clip.mp4"
    calls: list[Path] = []

    class FakeVideoConverter:
        def __init__(self, file_path: Path) -> None:
            calls.append(file_path)

        def run(self) -> Path:
            return calls[-1]

    monkeypatch.setattr(
        "src.conversion.conversion_phase.VideoConverter",
        FakeVideoConverter,
    )

    ConversionPhase(state_store)._process_video(video)

    assert calls == [video]
    assert state_store.get_status(video, "conversion") == "done"


def test_conversion_phase_skips_h264_video_when_av1_is_not_selected(
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    video = tmp_path / "clip.mp4"

    ConversionPhase(state_store)._process_video(video)

    assert state_store.get_status(video, "conversion") == "skipped"
