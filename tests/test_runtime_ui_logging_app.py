from __future__ import annotations

import logging
import os
import subprocess
from concurrent.futures import Future
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.config import Config
from src.helpers.phase_helpers import (
    handle_phase_keyboard_interrupt,
    log_resumed_stage_skip,
)
from src.logger.initialize_logs import InitializeLogs
from src.logger.log import APP_LOGGER_NAME, log
from src.metadata.media_datetime_reader import MediaDatetimeReader
from src.ui.update_ui import UpdateUI

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from src.core.state_store import StateStore


def test_initialize_logs_sets_logger_level_handler_and_retention(
    tmp_path: Path,
) -> None:
    Config.logs_folder = tmp_path / "logs"
    Config.logs_folder.mkdir()
    Config.cli_options["log_level"] = logging.INFO
    Config.cli_options["logs_amount"] = 3
    old = Config.logs_folder / "old.jsonl"
    middle = Config.logs_folder / "middle.jsonl"
    newest = Config.logs_folder / "newest.jsonl"
    for index, path in enumerate([old, middle, newest], start=1):
        path.write_text("old\n", encoding="utf-8")
        os.utime(path, (index, index))

    InitializeLogs()
    log("hello release logs", "info")

    logger = logging.getLogger(APP_LOGGER_NAME)
    jsonl_files = sorted(path.name for path in Config.logs_folder.glob("*.jsonl"))

    assert logger.level == logging.INFO
    assert logger.propagate is False
    assert len(logger.handlers) == 1
    assert len(jsonl_files) == 3
    assert middle.name in jsonl_files
    assert newest.name in jsonl_files
    assert old.name not in jsonl_files


def test_initialize_logs_build_helpers_create_expected_handler(tmp_path: Path) -> None:
    Config.logs_folder = tmp_path / "logs"
    Config.cli_options["log_level"] = logging.WARNING
    initializer = InitializeLogs.__new__(InitializeLogs)

    log_path = initializer._build_log_path()
    handler = initializer._create_file_handler(log_path)

    try:
        assert log_path.parent == Config.logs_folder
        assert log_path.suffix == ".jsonl"
        assert handler.level == logging.WARNING
        assert handler.formatter.__class__.__name__ == "JSONFormatter"
    finally:
        handler.close()


def test_update_ui_refresh_noops_before_first_phase(
    monkeypatch: pytest.MonkeyPatch,
    state_store: StateStore,
) -> None:
    rendered: list[str] = []

    class FakeDisplay:
        def __init__(self, *_args: object) -> None:
            rendered.append("init")

        def print_display(self, _state: str | None = None) -> None:
            rendered.append("print")

    monkeypatch.setattr("src.ui.update_ui.Display", FakeDisplay)

    UpdateUI(state_store).refresh()

    assert rendered == []


def test_update_ui_render_noops_before_first_phase(
    monkeypatch: pytest.MonkeyPatch,
    state_store: StateStore,
) -> None:
    rendered: list[str] = []

    class FakeDisplay:
        def __init__(self, *_args: object) -> None:
            rendered.append("init")

    monkeypatch.setattr("src.ui.update_ui.Display", FakeDisplay)

    UpdateUI(state_store)._render_locked()

    assert rendered == []


def test_update_ui_run_refreshes_and_clears_previous_display(
    monkeypatch: pytest.MonkeyPatch,
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    rendered: list[tuple[str, str | None, int]] = []
    cleared: list[int] = []

    class FakeDisplay:
        def __init__(
            self,
            _state_store: StateStore,
            stage: str,
            items: list[Path],
            _started_at: float,
        ) -> None:
            self.stage = stage
            self.items = items

        def print_display(self, state: str | None = None) -> None:
            rendered.append((self.stage, state, len(self.items)))

    monkeypatch.setattr("src.ui.update_ui.Display", FakeDisplay)
    monkeypatch.setattr(
        UpdateUI,
        "clear_display",
        staticmethod(lambda lines=8: cleared.append(lines)),
    )
    item = tmp_path / "photo.jpg"
    ui = UpdateUI(state_store, started_at=123.0)

    ui.run("loading", "overlay", [item])
    ui.refresh()
    ui.set_phase("metadata", [], "finished")

    assert rendered == [
        ("overlay", "loading", 1),
        ("overlay", "loading", 1),
        ("metadata", "finished", 0),
    ]
    assert cleared == [8, 8]


def test_update_ui_clear_display_writes_cursor_sequences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writes: list[str] = []
    monkeypatch.setattr("src.ui.update_ui.sys.stdout.write", writes.append)

    UpdateUI.clear_display(lines=3)

    assert writes == ["\033[F\033[K", "\033[F\033[K", "\033[F\033[K"]


def test_phase_helper_logs_resume_skip_messages(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger=APP_LOGGER_NAME)

    log_resumed_stage_skip("metadata", "photo.jpg", "done")
    log_resumed_stage_skip("metadata", "clip.mp4", "failed")

    assert "already done" in caplog.text
    assert "failed earlier" in caplog.text


def test_handle_phase_keyboard_interrupt_collects_unfinished_futures() -> None:
    done: Future[str] = Future()
    pending: Future[str] = Future()
    done.set_result("done")
    collected: list[dict[Future[str], str]] = []

    handle_phase_keyboard_interrupt(
        {done: "done-item", pending: "pending-item"},
        collected.append,
        "items",
    )

    assert collected == [{pending: "pending-item"}]


def test_media_datetime_reader_video_run_parses_ffmpeg_creation_time(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    Config.cli_options["ffmpeg_timeout"] = 7
    video = tmp_path / "clip.mp4"
    seen: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        seen["command"] = command
        seen["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            1,
            stderr="    creation_time   : 2024-05-01T12:30:45Z\n",
        )

    monkeypatch.setattr("src.metadata.media_datetime_reader.subprocess.run", fake_run)

    result = MediaDatetimeReader(video).run()

    assert result == datetime(2024, 5, 1, 12, 30, 45, tzinfo=UTC)
    assert seen["command"][1:] == ["-i", str(video)]
    assert seen["kwargs"]["timeout"] == 7
    assert seen["kwargs"]["check"] is False


def test_media_datetime_reader_video_run_returns_none_on_subprocess_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    video = tmp_path / "clip.mp4"

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired("ffmpeg", timeout=1)

    monkeypatch.setattr("src.metadata.media_datetime_reader.subprocess.run", fake_run)

    assert MediaDatetimeReader(video).run() is None


def test_media_datetime_reader_video_run_returns_none_without_creation_time(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    video = tmp_path / "clip.mp4"

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(command, 0, stderr="no creation metadata")

    monkeypatch.setattr("src.metadata.media_datetime_reader.subprocess.run", fake_run)

    assert MediaDatetimeReader(video).run() is None
