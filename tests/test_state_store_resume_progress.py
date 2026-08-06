from __future__ import annotations

from pathlib import Path

import src.core.state_store.state_store as state_store_module
from src.core.state_store import StageProgress, StateStore


def test_stage_progress_calculates_terminal_remaining_and_percent() -> None:
    progress = StageProgress(
        stage="metadata",
        total=5,
        done=2,
        failed=1,
        skipped=1,
    )

    assert progress.terminal == 4
    assert progress.remaining == 1
    assert progress.percent == 80.0
    assert StageProgress(stage="overlay", total=0).percent == 100.0


def test_stage_progress_clamps_percent_and_remaining() -> None:
    progress = StageProgress(stage="conversion", total=2, done=5)

    assert progress.terminal == 5
    assert progress.remaining == 0
    assert progress.percent == 100.0


def test_state_store_marks_running_and_done_with_attempt_count(
    state_store: StateStore,
) -> None:
    item = Path("2024-01-01-main.jpg")

    running = state_store.mark_running(item, "overlay")
    done = state_store.mark_done(item, "overlay")

    assert running.status == "running"
    assert running.attempts == 1
    assert done.status == "done"
    assert done.attempts == 1
    assert done.last_error is None
    assert state_store.get_status(item, "overlay") == "done"


def test_state_store_failed_from_pending_counts_as_attempt(
    state_store: StateStore,
) -> None:
    item = Path("bad-video.mp4")

    failed = state_store.mark_failed(item, "metadata", "ffmpeg failed")

    assert failed.status == "failed"
    assert failed.attempts == 1
    assert failed.last_error == "ffmpeg failed"


def test_state_store_failed_after_running_reuses_current_attempt(
    state_store: StateStore,
) -> None:
    item = Path("bad-image.jpg")

    state_store.mark_running(item, "conversion")
    failed = state_store.mark_failed(item, "conversion", "encoder failed")

    assert failed.status == "failed"
    assert failed.attempts == 1
    assert failed.last_error == "encoder failed"


def test_state_store_skipped_does_not_overwrite_done_or_failed(
    state_store: StateStore,
) -> None:
    done_item = Path("done.jpg")
    failed_item = Path("failed.jpg")
    state_store.mark_done(done_item, "overlay")
    state_store.mark_failed(failed_item, "overlay", "broken")

    assert state_store.mark_skipped(done_item, "overlay").status == "done"
    assert state_store.mark_skipped(failed_item, "overlay").status == "failed"
    assert state_store.get_status(done_item, "overlay") == "done"
    assert state_store.get_status(failed_item, "overlay") == "failed"


def test_state_store_summarizes_each_item_status(state_store: StateStore) -> None:
    done = Path("done.jpg")
    failed = Path("failed.jpg")
    skipped = Path("skipped.jpg")
    running = Path("running.jpg")
    pending = Path("pending.jpg")
    state_store.mark_done(done, "metadata")
    state_store.mark_failed(failed, "metadata", "missing json")
    state_store.mark_skipped(skipped, "metadata")
    state_store.mark_running(running, "metadata")

    progress = state_store.summarize_stage(
        [done, failed, skipped, running, pending],
        "metadata",
    )

    assert progress.total == 5
    assert progress.done == 1
    assert progress.failed == 1
    assert progress.skipped == 1
    assert progress.running == 1
    assert progress.pending == 1


def test_state_store_terminal_and_failed_stage_queries(
    state_store: StateStore,
) -> None:
    item = Path("video.mp4")
    state_store.mark_failed(item, "overlay", "overlay failed")

    assert state_store.terminal_status(item, "overlay") == "failed"
    assert state_store.terminal_status(item, "metadata") is None
    assert state_store.have_stage_failed(item, ("overlay", "metadata")) == "overlay"


def test_state_store_resets_running_and_retryable_statuses(
    state_store: StateStore,
) -> None:
    running = Path("running.jpg")
    failed = Path("failed.jpg")
    done = Path("done.jpg")
    state_store.mark_running(running, "overlay")
    state_store.mark_failed(failed, "overlay", "bad")
    state_store.mark_done(done, "overlay")

    state_store.reset_running()

    assert state_store.get_status(running, "overlay") == "pending"
    assert state_store.get_status(failed, "overlay") == "failed"

    state_store.reset_retryable()

    assert state_store.get_status(failed, "overlay") == "pending"
    assert state_store.get_status(done, "overlay") == "done"


def test_state_store_reset_retryable_noops_without_failed_status(
    state_store: StateStore,
) -> None:
    done = Path("done.jpg")
    state_store.mark_done(done, "overlay")

    state_store.reset_retryable()

    assert state_store.get_status(done, "overlay") == "done"


def test_state_store_clear_skipped_removes_only_skipped_stages(
    state_store: StateStore,
) -> None:
    item = Path("mixed.jpg")
    state_store.mark_skipped(item, "overlay")
    state_store.mark_done(item, "metadata")

    state_store.clear_skipped()

    assert state_store.get_status(item, "overlay") == "pending"
    assert state_store.get_status(item, "metadata") == "done"


def test_state_store_persists_state_to_disk(
    state_store: StateStore,
) -> None:
    item = Path("persisted.jpg")
    state_store.mark_done(item, "conversion")

    reloaded = state_store_module.StateStore()

    assert reloaded.get_status(item, "conversion") == "done"


def test_state_store_ignores_unknown_stage(state_store: StateStore) -> None:
    item = Path("unknown.jpg")

    state = state_store.mark_running(item, "unknown")

    assert state.status == "pending"
    assert state_store.get_status(item, "overlay") == "pending"


def test_state_store_unknown_stage_queries_return_empty_progress(
    state_store: StateStore,
) -> None:
    item = Path("unknown.jpg")

    assert state_store.get_status(item, "unknown") == "pending"
    assert state_store.summarize_stage([item], "unknown").total == 0
    assert state_store.mark_skipped(item, "unknown").status == "pending"
    assert state_store.mark_failed(item, "unknown", "bad").status == "pending"
