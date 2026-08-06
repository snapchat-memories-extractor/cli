from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from src.logger.error_descriptions import ERROR_DESCRIPTIONS
from src.logger.formatter import JSONFormatter
from src.logger.log import APP_LOGGER_NAME, log
from src.logger.phase_stats import PhaseStats
from src.ui.display import Display

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from src.core.state_store import StateStore


def test_json_formatter_formats_info_without_source_context() -> None:
    record = logging.LogRecord(
        APP_LOGGER_NAME,
        logging.INFO,
        __file__,
        10,
        "hello",
        (),
        None,
    )

    payload = json.loads(JSONFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["message"] == "hello"
    assert "timestamp" in payload
    assert "file_path" not in payload
    assert "error_code" not in payload


def test_json_formatter_adds_error_descriptions_and_context() -> None:
    record = logging.LogRecord(
        APP_LOGGER_NAME,
        logging.ERROR,
        __file__,
        12,
        "missing",
        (),
        None,
        func="test_func",
    )
    record.error_code = "MISS"

    payload = json.loads(JSONFormatter().format(record))

    assert payload["level"] == "ERROR"
    assert payload["error_code"] == "MISS"
    assert payload["error_message"] == ERROR_DESCRIPTIONS["MISS"]
    assert payload["file_path"] == __file__
    assert payload["function"] == "test_func"
    assert payload["line"] == 12


def test_log_attaches_error_code_to_error_records(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.ERROR, logger=APP_LOGGER_NAME)

    log("missing path", "error", "MISS")

    assert caplog.records[0].getMessage() == "missing path"
    assert caplog.records[0].error_code == "MISS"


def test_log_does_not_attach_error_code_to_non_error_records(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=APP_LOGGER_NAME)

    log("careful", "warning", "MISS")

    assert caplog.records[0].getMessage() == "careful"
    assert not hasattr(caplog.records[0], "error_code")


def test_phase_stats_tracks_counts_and_logs_summary(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=APP_LOGGER_NAME)
    stats = PhaseStats("metadata")

    stats.mark("done", "photo.jpg")
    stats.mark("skipped", "notes.txt", "unsupported")
    stats.mark("failed", "clip.mp4", "ffmpeg failed")
    stats.log_summary()

    assert stats.counts["done"] == 1
    assert stats.counts["skipped"] == 1
    assert stats.counts["failed"] == 1
    assert "Metadata phase summary: succeeded=1, skipped=1, failed=1." in caplog.text


def test_display_progress_bar_handles_empty_and_clamped_progress() -> None:
    assert Display._generate_progress_bar(0, 0, 5) == "#####"
    assert Display._generate_progress_bar(3, 6, 6) == "###---"
    assert Display._generate_progress_bar(10, 5, 5) == "#####"
    assert Display._generate_progress_bar(-1, 5, 5) == "-----"


def test_display_eta_and_time_formatting() -> None:
    assert Display._calculate_eta(current=0, elapsed_time=10, remaining=5) == (
        "calculating..."
    )
    assert Display._calculate_eta(current=5, elapsed_time=10, remaining=0) == "0s"
    assert Display._calculate_eta(current=5, elapsed_time=10, remaining=10) == "20s"
    assert Display._format_time(59) == "59s"
    assert Display._format_time(61) == "1m 1s"
    assert Display._format_time(3661) == "1h 1m"


def test_display_padding_truncates_long_content() -> None:
    assert Display._padding_line("abc", total_width=5) == "abc  "
    assert Display._padding_line("abcdef", total_width=5) == "ab..."


def test_display_reads_state_store_progress(
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.jpg"
    second = tmp_path / "second.jpg"
    state_store.mark_done(first, "overlay")
    state_store.mark_skipped(second, "overlay")

    display = Display(
        state_store=state_store,
        stage="overlay",
        items=[first, second],
        started_at=0,
    )

    assert display.phase_index == 1
    assert display.progress.total == 2
    assert display.progress.terminal == 2
    assert display.progress.percent == 100.0
    assert display.eta == "0s"


def test_display_prints_bordered_status(
    capsys: pytest.CaptureFixture[str],
    state_store: StateStore,
) -> None:
    Display(
        state_store=state_store,
        stage="conversion",
        items=[],
        started_at=0,
    ).print_display("finished")

    output = capsys.readouterr().out

    assert "SNAPCHAT MEMORIES DOWNLOADER" in output
    assert "PHASE 3/3" in output
    assert "Processing complete." in output
    assert "Conversion" in output


def test_display_prints_loading_interrupted_and_base_statuses(
    capsys: pytest.CaptureFixture[str],
    state_store: StateStore,
) -> None:
    display = Display(
        state_store=state_store,
        stage="overlay",
        items=[],
        started_at=0,
    )

    display.print_display("loading")
    display.print_display("interrupted")
    display.print_display()

    output = capsys.readouterr().out

    assert "Preparing pipeline state." in output
    assert "Processing interrupted by user." in output
    assert "Done 0 | Running 0 | Skipped 0 | Failed 0" in output
