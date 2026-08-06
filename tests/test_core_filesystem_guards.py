from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Config
from src.core.app import App
from src.core.ensure_directories import ensure_directories
from src.core.fail_fast_checks import fail_fast_checks
from src.helpers import (
    is_image,
    is_supported_media,
    is_video,
    overlay_phase_items,
    scan_memory_files,
    scan_output_files,
)


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"file")
    return path


def test_media_type_helpers_accept_supported_suffixes_case_insensitively() -> None:
    assert is_image(Path("photo.JPG"))
    assert is_image(Path("photo.jpeg"))
    assert is_video(Path("clip.MP4"))
    assert is_supported_media(Path("photo.JPEG"))
    assert is_supported_media(Path("clip.mp4"))


def test_media_type_helpers_reject_non_export_media() -> None:
    assert not is_image(Path("overlay.png"))
    assert not is_video(Path("photo.jpg"))
    assert not is_supported_media(Path("notes.txt"))
    assert not is_supported_media(Path("image.webp"))


def test_scan_memory_files_returns_sorted_direct_files_only() -> None:
    _touch(Config.memories_folder / "b-main.jpg")
    _touch(Config.memories_folder / "a-main.mp4")
    (Config.memories_folder / "nested").mkdir()
    _touch(Config.memories_folder / "nested" / "hidden-main.jpg")

    assert [path.name for path in scan_memory_files()] == [
        "a-main.mp4",
        "b-main.jpg",
    ]


def test_scan_memory_files_logs_and_reraises_scan_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class BrokenFolder:
        def iterdir(self) -> object:
            error_message = "folder locked"
            raise OSError(error_message)

        def __str__(self) -> str:
            return "broken-folder"

    Config.memories_folder = BrokenFolder()

    with pytest.raises(OSError, match="folder locked"):
        scan_memory_files()

    assert "Failed to scan memories folder at broken-folder" in caplog.text


def test_scan_output_files_excludes_overlay_layers() -> None:
    _touch(Config.output_folder / "2024-01-01-main.jpg")
    _touch(Config.output_folder / "2024-01-01-overlay.png")
    _touch(Config.output_folder / "2024-01-01-overlaid.mp4")
    _touch(Config.output_folder / "notes.txt")

    assert [path.name for path in scan_output_files()] == [
        "2024-01-01-main.jpg",
        "2024-01-01-overlaid.mp4",
        "notes.txt",
    ]


def test_overlay_phase_items_selects_main_and_existing_overlaid_files() -> None:
    _touch(Config.memories_folder / "one-main.jpg")
    _touch(Config.memories_folder / "one-overlay.png")
    _touch(Config.memories_folder / "two-overlaid.mp4")
    _touch(Config.memories_folder / "loose.txt")

    assert [path.name for path in overlay_phase_items()] == [
        "one-main.jpg",
        "two-overlaid.mp4",
    ]


def test_ensure_directories_creates_output_and_logs_folders(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "output"
    logs = tmp_path / "nested" / "logs"

    ensure_directories(output, logs)

    assert output.is_dir()
    assert logs.is_dir()


def test_fail_fast_allows_missing_json_when_metadata_is_disabled() -> None:
    Config.cli_options["write_metadata"] = False
    Config.memories_folder.mkdir()

    assert fail_fast_checks()


def test_fail_fast_requires_json_when_metadata_is_enabled(
    caplog: pytest.LogCaptureFixture,
) -> None:
    Config.memories_folder.mkdir()

    assert not fail_fast_checks()
    assert "Missing memories JSON file" in caplog.text


def test_fail_fast_rejects_missing_memories_folder_even_without_metadata(
    caplog: pytest.LogCaptureFixture,
) -> None:
    Config.cli_options["write_metadata"] = False

    assert not fail_fast_checks()
    assert "Missing memories folder" in caplog.text


def test_fail_fast_rejects_output_inside_memories_folder(
    caplog: pytest.LogCaptureFixture,
) -> None:
    Config.memories_folder.mkdir()
    Config.json_path.write_text('{"Saved Media": []}', encoding="utf-8")
    Config.output_folder = Config.memories_folder / "output"

    assert not fail_fast_checks()
    assert "Output directory must be separate" in caplog.text


def test_app_prepare_state_deletes_before_resetting_running_state() -> None:
    class Store:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def delete(self) -> None:
            self.calls.append("delete")

        def reset_retryable(self) -> None:
            self.calls.append("retry")

        def reset_running(self) -> None:
            self.calls.append("running")

    Config.cli_options["reset_state"] = True
    Config.cli_options["retry_failed"] = True
    store = Store()

    App._prepare_state(store)

    assert store.calls == ["delete", "running"]


def test_app_prepare_state_retries_failed_when_requested() -> None:
    class Store:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def delete(self) -> None:
            self.calls.append("delete")

        def reset_retryable(self) -> None:
            self.calls.append("retry")

        def reset_running(self) -> None:
            self.calls.append("running")

    Config.cli_options["retry_failed"] = True
    store = Store()

    App._prepare_state(store)

    assert store.calls == ["retry", "running"]
