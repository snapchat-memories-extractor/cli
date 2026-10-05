from __future__ import annotations

import os
import subprocess
from pathlib import Path

import piexif
import pytest
from PIL import Image

from src.config import Config
from src.overlay.image_composer import ImageComposer
from src.overlay.overlay_job import _composite, overlay_output_path, run_overlay_job
from src.overlay.overlay_phase import OverlayPhase
from src.overlay.scan_overlay_pairs import (
    OverlayPair,
    _parse_filename,
    scan_overlay_pairs,
)
from src.overlay.video_composer import VideoComposer


def _touch(path: Path, content: bytes = b"file") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_parse_filename_identifies_main_overlay_and_ignores_other_files() -> None:
    assert _parse_filename(Path("abc-main.jpg")) == ("abc", "main")
    assert _parse_filename(Path("abc-overlay.png")) == ("abc", "overlay")
    assert _parse_filename(Path("abc-overlaid.jpg")) is None
    assert _parse_filename(Path("abc.txt")) is None


def test_scan_overlay_pairs_matches_pairs_in_media_id_order(
    caplog: pytest.LogCaptureFixture,
) -> None:
    _touch(Config.memories_folder / "b-main.jpg")
    _touch(Config.memories_folder / "b-overlay.png")
    _touch(Config.memories_folder / "a-main.mp4")
    _touch(Config.memories_folder / "a-overlay.png")
    _touch(Config.memories_folder / "lonely-overlay.png")
    _touch(Config.memories_folder / "plain-main.jpg")

    pairs = scan_overlay_pairs()

    assert [pair.media_id for pair in pairs] == ["a", "b"]
    assert pairs[0].main_path.name == "a-main.mp4"
    assert pairs[1].overlay_path.name == "b-overlay.png"
    assert "no matching main" in caplog.text


def test_overlay_output_path_uses_output_folder_media_id_and_main_suffix() -> None:
    pair = OverlayPair(
        media_id="2024-01-01_001",
        main_path=Path("source/2024-01-01_001-main.mp4"),
        overlay_path=Path("source/2024-01-01_001-overlay.png"),
    )

    assert overlay_output_path(pair) == Config.output_folder / (
        "2024-01-01_001-overlaid.mp4"
    )


def test_image_composer_applies_resized_overlay_and_saves_jpeg(
    tmp_path: Path,
) -> None:
    Config.cli_options["jpeg_quality"] = 100
    main = tmp_path / "one-main.jpg"
    overlay = tmp_path / "one-overlay.png"
    output = tmp_path / "one-overlaid.jpg"
    Image.new("RGB", (2, 2), (0, 0, 0)).save(main, format="JPEG")
    Image.new("RGBA", (1, 1), (0, 255, 0, 255)).save(overlay, format="PNG")
    pair = OverlayPair("one", main, overlay)

    ImageComposer(pair, output).apply_overlay()

    with Image.open(output) as result:
        red, green, blue = result.getpixel((0, 0))
        assert result.mode == "RGB"
        assert result.size == (2, 2)
        assert red < 10
        assert green > 240
        assert blue < 10


def test_image_composer_preserves_existing_exif_when_present(tmp_path: Path) -> None:
    Config.cli_options["jpeg_quality"] = 100
    main = tmp_path / "one-main.jpg"
    overlay = tmp_path / "one-overlay.png"
    output = tmp_path / "one-overlaid.jpg"
    exif = {"0th": {piexif.ImageIFD.Make: b"Snapchat"}}
    Image.new("RGB", (2, 2), (0, 0, 0)).save(
        main,
        format="JPEG",
        exif=piexif.dump(exif),
    )
    Image.new("RGBA", (2, 2), (0, 255, 0, 255)).save(overlay, format="PNG")

    ImageComposer(OverlayPair("one", main, overlay), output).apply_overlay()

    assert piexif.load(str(output))["0th"][piexif.ImageIFD.Make] == b"Snapchat"


def test_image_composer_helpers_reuse_already_matching_images() -> None:
    image = Image.new("RGBA", (2, 2), (0, 0, 0, 0))

    assert ImageComposer._ensure_rgba(image) is image
    assert ImageComposer._resize_to_match(image, (2, 2)) is image


def test_video_composer_reuses_overlay_when_size_already_matches(
    tmp_path: Path,
) -> None:
    overlay = tmp_path / "clip-overlay.png"
    Image.new("RGBA", (4, 3), (255, 0, 0, 128)).save(overlay, format="PNG")
    pair = OverlayPair("clip", tmp_path / "clip-main.mp4", overlay)

    composer = VideoComposer(pair, tmp_path / "clip-overlaid.mp4")
    resolved = composer._resolve_overlay_path(4, 3)

    assert resolved == overlay


def test_video_composer_resizes_mismatched_overlay_to_temporary_png(
    tmp_path: Path,
) -> None:
    overlay = tmp_path / "clip-overlay.png"
    Image.new("RGBA", (1, 1), (255, 0, 0, 128)).save(overlay, format="PNG")
    pair = OverlayPair("clip", tmp_path / "clip-main.mp4", overlay)
    composer = VideoComposer(pair, tmp_path / "clip-overlaid.mp4")

    resized = composer._resolve_overlay_path(4, 3)

    try:
        assert resized != overlay
        assert resized.exists()
        with Image.open(resized) as image:
            assert image.size == (4, 3)
    finally:
        resized.unlink(missing_ok=True)


def test_video_composer_reads_dimensions_and_closes_reader(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class FakeReader:
        def __init__(self) -> None:
            self.closed = False

        def __next__(self) -> dict[str, tuple[str, str]]:
            return {"source_size": ("640", "480")}

        def close(self) -> None:
            self.closed = True

    reader = FakeReader()
    monkeypatch.setattr(
        "src.overlay.video_composer.read_frames",
        lambda _path: reader,
    )

    assert VideoComposer._get_video_dimensions(tmp_path / "clip.mp4") == (640, 480)
    assert reader.closed


def test_video_composer_apply_overlay_removes_temporary_overlay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pair = OverlayPair(
        "clip",
        _touch(tmp_path / "clip-main.mp4"),
        _touch(tmp_path / "clip-overlay.png"),
    )
    temp_overlay = _touch(tmp_path / "temporary-overlay.png")
    output = tmp_path / "clip-overlaid.mp4"
    calls: list[object] = []

    monkeypatch.setattr(
        VideoComposer,
        "_get_video_dimensions",
        staticmethod(lambda _path: (4, 3)),
    )
    monkeypatch.setattr(
        VideoComposer,
        "_resolve_overlay_path",
        lambda _self, _width, _height: temp_overlay,
    )
    monkeypatch.setattr(
        VideoComposer,
        "_build_ffmpeg_overlay_command",
        lambda _self, overlay_path: calls.append(overlay_path) or ["ffmpeg"],
    )
    monkeypatch.setattr(
        VideoComposer,
        "_run_ffmpeg_command",
        lambda _self, command: calls.append(command),
    )

    VideoComposer(pair, output).apply_overlay()

    assert calls == [temp_overlay, ["ffmpeg"]]
    assert not temp_overlay.exists()


def test_video_composer_apply_overlay_keeps_original_overlay(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pair = OverlayPair(
        "clip",
        _touch(tmp_path / "clip-main.mp4"),
        _touch(tmp_path / "clip-overlay.png"),
    )
    calls: list[object] = []

    monkeypatch.setattr(
        VideoComposer,
        "_get_video_dimensions",
        staticmethod(lambda _path: (4, 3)),
    )
    monkeypatch.setattr(
        VideoComposer,
        "_resolve_overlay_path",
        lambda self, _width, _height: self.overlay_path,
    )
    monkeypatch.setattr(
        VideoComposer,
        "_build_ffmpeg_overlay_command",
        lambda _self, overlay_path: calls.append(overlay_path) or ["ffmpeg"],
    )
    monkeypatch.setattr(
        VideoComposer,
        "_run_ffmpeg_command",
        lambda _self, command: calls.append(command),
    )

    VideoComposer(pair, tmp_path / "clip-overlaid.mp4").apply_overlay()

    assert calls == [pair.overlay_path, ["ffmpeg"]]
    assert pair.overlay_path.exists()


def test_video_composer_run_ffmpeg_command_uses_timeout_and_hidden_window(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    Config.cli_options["ffmpeg_timeout"] = 11
    pair = OverlayPair(
        "clip",
        tmp_path / "clip-main.mp4",
        tmp_path / "clip-overlay.png",
    )
    seen: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        seen["command"] = command
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("src.overlay.video_composer.subprocess.run", fake_run)

    result = VideoComposer(pair, tmp_path / "out.mp4")._run_ffmpeg_command(["ffmpeg"])

    assert result.returncode == 0
    assert seen["command"] == ["ffmpeg"]
    assert seen["kwargs"]["check"] is True
    assert seen["kwargs"]["timeout"] == 11
    assert seen["kwargs"]["capture_output"] is True


def test_video_composer_builds_expected_ffmpeg_overlay_command(
    tmp_path: Path,
) -> None:
    Config.cli_options.update(
        {
            "overlay_video_crf": 23,
            "overlay_video_preset": "slow",
            "overlay_video_pixel_format": "yuv444p",
        }
    )
    pair = OverlayPair(
        "clip",
        tmp_path / "clip-main.mp4",
        tmp_path / "clip-overlay.png",
    )
    output = tmp_path / "clip-overlaid.mp4"

    command = VideoComposer(pair, output)._build_ffmpeg_overlay_command(
        pair.overlay_path,
    )

    assert command[1:5] == ["-y", "-i", str(pair.main_path), "-i"]
    assert command[5] == str(pair.overlay_path)
    assert command[6:8] == ["-filter_complex", "overlay=0:0"]
    assert command[10:16] == ["-c:v", "libx264", "-crf", "23", "-preset", "slow"]
    assert command[-5:] == ["-pix_fmt", "yuv444p", "-c:a", "copy", str(output)]


def test_run_overlay_job_replaces_temp_output_and_preserves_main_stats(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    Config.output_folder = tmp_path / "output"
    main = _touch(tmp_path / "one-main.jpg", b"main")
    overlay = _touch(tmp_path / "one-overlay.png", b"overlay")
    os.utime(main, (1_700_000_000, 1_700_000_000))
    pair = OverlayPair("one", main, overlay)

    def fake_composite(composite_pair: OverlayPair, output_path: Path) -> None:
        assert composite_pair == pair
        assert output_path.name == "one-overlaid.compositing.jpg"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"composited")

    monkeypatch.setattr("src.overlay.overlay_job._composite", fake_composite)

    result = run_overlay_job(pair)

    assert result == Config.output_folder / "one-overlaid.jpg"
    assert result.read_bytes() == b"composited"
    assert not (Config.output_folder / "one-overlaid.compositing.jpg").exists()
    assert abs(result.stat().st_mtime - main.stat().st_mtime) < 1


def test_run_overlay_job_removes_empty_temp_output_and_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    Config.output_folder = tmp_path / "output"
    main = _touch(tmp_path / "one-main.jpg", b"main")
    overlay = _touch(tmp_path / "one-overlay.png", b"overlay")
    pair = OverlayPair("one", main, overlay)

    def fake_composite(_pair: OverlayPair, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"")

    monkeypatch.setattr("src.overlay.overlay_job._composite", fake_composite)

    with pytest.raises(RuntimeError, match="no usable output"):
        run_overlay_job(pair)

    assert not (Config.output_folder / "one-overlaid.compositing.jpg").exists()
    assert not (Config.output_folder / "one-overlaid.jpg").exists()


def test_run_overlay_job_removes_temp_output_when_composite_raises(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    Config.output_folder = tmp_path / "output"
    main = _touch(tmp_path / "one-main.jpg", b"main")
    overlay = _touch(tmp_path / "one-overlay.png", b"overlay")
    pair = OverlayPair("one", main, overlay)

    def fake_composite(_pair: OverlayPair, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"partial")
        error_message = "composition crashed"
        raise RuntimeError(error_message)

    monkeypatch.setattr("src.overlay.overlay_job._composite", fake_composite)

    with pytest.raises(RuntimeError, match="composition crashed"):
        run_overlay_job(pair)

    assert not (Config.output_folder / "one-overlaid.compositing.jpg").exists()
    assert not (Config.output_folder / "one-overlaid.jpg").exists()


def test_composite_dispatches_to_video_or_image_composer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, Path]] = []

    class FakeImageComposer:
        def __init__(self, _pair: OverlayPair, output_path: Path) -> None:
            self.output_path = output_path

        def apply_overlay(self) -> None:
            calls.append(("image", self.output_path))

    class FakeVideoComposer:
        def __init__(self, _pair: OverlayPair, output_path: Path) -> None:
            self.output_path = output_path

        def apply_overlay(self) -> None:
            calls.append(("video", self.output_path))

    monkeypatch.setattr("src.overlay.overlay_job.ImageComposer", FakeImageComposer)
    monkeypatch.setattr("src.overlay.overlay_job.VideoComposer", FakeVideoComposer)

    image_output = tmp_path / "image.jpg"
    video_output = tmp_path / "video.mp4"
    image_pair = OverlayPair("image", Path("image-main.jpg"), Path("image.png"))
    video_pair = OverlayPair("video", Path("video-main.mp4"), Path("video.png"))

    _composite(image_pair, image_output)
    _composite(video_pair, video_output)

    assert calls == [("image", image_output), ("video", video_output)]


def test_overlay_phase_copy_to_output_noops_when_source_is_already_output(
    tmp_path: Path,
) -> None:
    Config.output_folder = tmp_path
    path = _touch(tmp_path / "already-output-main.jpg", b"same")

    assert OverlayPhase._copy_to_output(path) == path
    assert path.read_bytes() == b"same"
