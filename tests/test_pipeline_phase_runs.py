from __future__ import annotations

from concurrent.futures import Future
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import piexif
import pytest
from PIL import Image

from src.config import Config
from src.conversion.conversion_phase import ConversionPhase
from src.core.app import App
from src.metadata.json_memory_loader import Memory
from src.metadata.metadata_phase import (
    MetadataPhase,
)
from src.metadata.metadata_phase import (
    _terminal_status_skip_reason as metadata_skip_reason,
)
from src.overlay.overlay_phase import (
    OverlayPhase,
)
from src.overlay.overlay_phase import (
    _terminal_status_skip_reason as overlay_skip_reason,
)
from src.overlay.scan_overlay_pairs import OverlayPair

if TYPE_CHECKING:
    from src.core.state_store import StateStore


def _touch(path: Path, content: bytes = b"file") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_overlay_phase_run_off_copies_main_files_and_marks_skipped(
    state_store: StateStore,
) -> None:
    Config.cli_options["overlay_mode"] = "off"
    main = _touch(Config.memories_folder / "one-main.jpg", b"main")
    _touch(Config.memories_folder / "one-overlay.png", b"overlay")
    _touch(Config.memories_folder / "notmain.jpg", b"other")

    OverlayPhase(state_store).run()

    assert (Config.output_folder / "one-main.jpg").read_bytes() == b"main"
    assert not (Config.output_folder / "notmain.jpg").exists()
    assert state_store.get_status(main, "overlay") == "skipped"


def test_overlay_phase_run_on_processes_pairs_and_copies_passthrough_files(
    monkeypatch: pytest.MonkeyPatch,
    state_store: StateStore,
) -> None:
    Config.cli_options["overlay_mode"] = "on"
    main = _touch(Config.memories_folder / "pair-main.jpg", b"main")
    overlay = _touch(Config.memories_folder / "pair-overlay.png", b"overlay")
    unpaired = _touch(Config.memories_folder / "solo-main.jpg", b"solo")
    existing = _touch(Config.memories_folder / "ready-overlaid.jpg", b"ready")
    processed: list[str] = []

    def fake_run_overlay_job(pair: OverlayPair) -> Path:
        processed.append(pair.media_id)
        output = Config.output_folder / f"{pair.media_id}-overlaid.jpg"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"overlaid")
        return output

    monkeypatch.setattr(
        "src.overlay.overlay_phase.run_overlay_job",
        fake_run_overlay_job,
    )

    OverlayPhase(state_store).run()

    assert processed == ["pair"]
    assert (Config.output_folder / "pair-overlaid.jpg").read_bytes() == b"overlaid"
    assert (Config.output_folder / "solo-main.jpg").read_bytes() == b"solo"
    assert (Config.output_folder / "ready-overlaid.jpg").read_bytes() == b"ready"
    assert state_store.get_status(main, "overlay") == "done"
    assert state_store.get_status(overlay, "overlay") == "done"
    assert state_store.get_status(unpaired, "overlay") == "skipped"
    assert state_store.get_status(existing, "overlay") == "done"


def test_overlay_phase_run_both_keeps_clean_main_and_overlaid_copy(
    monkeypatch: pytest.MonkeyPatch,
    state_store: StateStore,
) -> None:
    Config.cli_options["overlay_mode"] = "both"
    main = _touch(Config.memories_folder / "pair-main.jpg", b"main")
    _touch(Config.memories_folder / "pair-overlay.png", b"overlay")

    def fake_run_overlay_job(pair: OverlayPair) -> Path:
        output = Config.output_folder / f"{pair.media_id}-overlaid.jpg"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"overlaid")
        return output

    monkeypatch.setattr(
        "src.overlay.overlay_phase.run_overlay_job",
        fake_run_overlay_job,
    )

    OverlayPhase(state_store).run()

    assert (Config.output_folder / "pair-main.jpg").read_bytes() == b"main"
    assert (Config.output_folder / "pair-overlaid.jpg").read_bytes() == b"overlaid"
    assert state_store.get_status(Config.output_folder / "pair-main.jpg", "overlay")
    assert state_store.get_status(main, "overlay") == "done"


def test_overlay_phase_collect_results_marks_failed_pair(
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    pair = OverlayPair(
        "bad",
        tmp_path / "bad-main.jpg",
        tmp_path / "bad-overlay.png",
    )
    future: Future[None] = Future()
    future.set_exception(RuntimeError("overlay broke"))

    OverlayPhase(state_store)._collect_results({future: pair})

    assert state_store.get_status(pair.main_path, "overlay") == "failed"
    assert state_store.get_status(pair.overlay_path, "overlay") == "failed"


def test_overlay_phase_terminal_done_is_ignored_when_output_is_missing(
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    pair = OverlayPair(
        "missing-output",
        tmp_path / "missing-output-main.jpg",
        tmp_path / "missing-output-overlay.png",
    )
    state_store.mark_done(pair.main_path, "overlay")

    assert OverlayPhase(state_store)._terminal_overlay_status(pair) is None


def test_overlay_phase_terminal_failed_blocks_pair(
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    pair = OverlayPair(
        "failed",
        tmp_path / "failed-main.jpg",
        tmp_path / "failed-overlay.png",
    )
    state_store.mark_failed(pair.overlay_path, "overlay", "old failure")

    assert OverlayPhase(state_store)._terminal_overlay_status(pair) == "failed"


def test_overlay_phase_run_reports_no_pairs_when_folder_has_no_work(
    state_store: StateStore,
) -> None:
    Config.memories_folder.mkdir()

    OverlayPhase(state_store).run()

    assert not Config.output_folder.exists()


def test_overlay_phase_run_finishes_in_flight_work_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    state_store: StateStore,
) -> None:
    main = _touch(Config.memories_folder / "pair-main.jpg", b"main")
    _touch(Config.memories_folder / "pair-overlay.png", b"overlay")
    handled: list[tuple[dict[object, object], str]] = []

    monkeypatch.setattr(
        OverlayPhase,
        "_submit_pairs",
        lambda _self, _executor, pairs: {"future": pairs[0]},
    )
    monkeypatch.setattr(
        OverlayPhase,
        "_collect_results",
        lambda _self, _futures: (_ for _ in ()).throw(KeyboardInterrupt),
    )
    monkeypatch.setattr(
        "src.overlay.overlay_phase.handle_phase_keyboard_interrupt",
        lambda futures, _collector, work_name: handled.append((futures, work_name)),
    )

    OverlayPhase(state_store).run()

    assert handled == [
        (
            {"future": OverlayPair("pair", main, main.with_name("pair-overlay.png"))},
            "overlays",
        )
    ]


def test_overlay_phase_apply_overlay_requires_existing_main_file(
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    pair = OverlayPair(
        "missing",
        tmp_path / "missing-main.jpg",
        tmp_path / "missing-overlay.png",
    )

    with pytest.raises(FileNotFoundError):
        OverlayPhase(state_store)._apply_overlay(pair)


def test_overlay_phase_filter_resumable_pairs_skips_terminal_statuses(
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    done_pair = OverlayPair(
        "done",
        tmp_path / "done-main.jpg",
        tmp_path / "done-overlay.png",
    )
    failed_pair = OverlayPair(
        "failed",
        tmp_path / "failed-main.jpg",
        tmp_path / "failed-overlay.png",
    )
    eligible_pair = OverlayPair(
        "eligible",
        tmp_path / "eligible-main.jpg",
        tmp_path / "eligible-overlay.png",
    )
    Config.output_folder.mkdir()
    _touch(Config.output_folder / "done-overlaid.jpg")
    state_store.mark_done(done_pair.main_path, "overlay")
    state_store.mark_failed(failed_pair.overlay_path, "overlay", "old failure")

    eligible = OverlayPhase(state_store)._filter_resumable_pairs(
        [done_pair, failed_pair, eligible_pair]
    )

    assert eligible == [eligible_pair]


def test_overlay_phase_terminal_status_skip_reason_text() -> None:
    assert overlay_skip_reason("failed") == "it failed earlier"
    assert overlay_skip_reason("done") == "it is already done"


def test_metadata_phase_run_marks_all_skipped_when_disabled(
    state_store: StateStore,
) -> None:
    Config.cli_options["write_metadata"] = False
    image = _touch(Config.output_folder / "2024-01-01-main.jpg")
    video = _touch(Config.output_folder / "2024-01-01-main.mp4")

    MetadataPhase(state_store).run()

    assert state_store.get_status(image, "metadata") == "skipped"
    assert state_store.get_status(video, "metadata") == "skipped"


def test_metadata_phase_run_returns_when_output_folder_is_empty(
    state_store: StateStore,
) -> None:
    Config.output_folder.mkdir()

    MetadataPhase(state_store).run()

    assert state_store.summarize_stage([], "metadata").total == 0


def test_metadata_phase_run_reports_no_eligible_media_after_filtering(
    state_store: StateStore,
) -> None:
    unsupported = _touch(Config.output_folder / "notes.txt")

    MetadataPhase(state_store).run()

    assert state_store.get_status(unsupported, "metadata") == "skipped"


def test_metadata_phase_run_matches_media_and_writes_metadata(
    monkeypatch: pytest.MonkeyPatch,
    state_store: StateStore,
) -> None:
    image = _touch(Config.output_folder / "2024-01-01-image.jpg")
    video = _touch(Config.output_folder / "2024-01-01-video.mp4")
    notes = _touch(Config.output_folder / "notes.txt")
    memories = [
        Memory(
            captured_at=datetime(2024, 1, 1, 8, 0, tzinfo=UTC),
            location_coords=(1.0, 2.0),
        ),
        Memory(
            captured_at=datetime(2024, 1, 1, 9, 0, tzinfo=UTC),
            location_coords=(3.0, 4.0),
        ),
    ]
    written: list[Path] = []

    monkeypatch.setattr(
        "src.metadata.metadata_phase.load_json_memories",
        lambda: memories,
    )
    monkeypatch.setattr(
        MetadataPhase,
        "_write_metadata",
        staticmethod(lambda _memory, path: written.append(path)),
    )

    MetadataPhase(state_store).run()

    assert written == [image, video]
    assert memories[0].file_path == image
    assert memories[1].file_path == video
    assert state_store.get_status(image, "metadata") == "done"
    assert state_store.get_status(video, "metadata") == "done"
    assert state_store.get_status(notes, "metadata") == "skipped"


def test_metadata_phase_run_marks_unmatched_media_skipped(
    monkeypatch: pytest.MonkeyPatch,
    state_store: StateStore,
) -> None:
    image = _touch(Config.output_folder / "2024-01-01-image.jpg")
    monkeypatch.setattr("src.metadata.metadata_phase.load_json_memories", list)

    MetadataPhase(state_store).run()

    assert state_store.get_status(image, "metadata") == "skipped"


def test_metadata_phase_filters_blocked_and_resumable_media(
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    blocked = tmp_path / "blocked.jpg"
    done = tmp_path / "done.jpg"
    eligible = tmp_path / "eligible.jpg"
    state_store.mark_failed(blocked, "overlay", "overlay failed")
    state_store.mark_done(done, "metadata")
    phase = MetadataPhase(state_store)

    after_blocked = phase._filter_blocked_media([blocked, done, eligible])
    after_resumable = phase._filter_resumable_media(after_blocked)

    assert after_blocked == [done, eligible]
    assert after_resumable == [eligible]
    assert state_store.get_status(blocked, "metadata") == "skipped"


def test_metadata_phase_collect_results_marks_failed_file(
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "bad.jpg"
    future: Future[None] = Future()
    future.set_exception(RuntimeError("metadata broke"))

    MetadataPhase(state_store)._collect_results({future: file_path})

    assert state_store.get_status(file_path, "metadata") == "failed"


def test_metadata_phase_run_finishes_in_flight_work_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    state_store: StateStore,
) -> None:
    image = _touch(Config.output_folder / "2024-01-01-image.jpg")
    memory = Memory(
        captured_at=datetime(2024, 1, 1, 8, 0, tzinfo=UTC),
        location_coords=(1.0, 2.0),
    )
    handled: list[tuple[dict[object, object], str]] = []

    monkeypatch.setattr(
        "src.metadata.metadata_phase.load_json_memories",
        lambda: [memory],
    )
    monkeypatch.setattr(
        MetadataPhase,
        "_submit_memories",
        lambda _self, _executor, _memories: {"future": image},
    )
    monkeypatch.setattr(
        MetadataPhase,
        "_collect_results",
        lambda _self, _futures: (_ for _ in ()).throw(KeyboardInterrupt),
    )
    monkeypatch.setattr(
        "src.metadata.metadata_phase.handle_phase_keyboard_interrupt",
        lambda futures, _collector, work_name: handled.append((futures, work_name)),
    )

    MetadataPhase(state_store).run()

    assert handled == [({"future": image}, "metadata writes")]


def test_metadata_phase_terminal_status_skip_reason_text() -> None:
    assert metadata_skip_reason("failed") == "it failed earlier"
    assert metadata_skip_reason("done") == "it is already done"


def test_metadata_phase_memory_file_path_requires_match() -> None:
    memory = Memory(
        captured_at=datetime(2024, 1, 1, tzinfo=UTC),
        location_coords=(1.0, 2.0),
    )

    with pytest.raises(ValueError):
        MetadataPhase._memory_file_path(memory)


def test_conversion_phase_run_marks_all_skipped_when_disabled(
    state_store: StateStore,
) -> None:
    image = _touch(Config.output_folder / "photo.jpg")
    video = _touch(Config.output_folder / "clip.mp4")

    ConversionPhase(state_store).run()

    assert state_store.get_status(image, "conversion") == "skipped"
    assert state_store.get_status(video, "conversion") == "skipped"


def test_conversion_phase_run_reports_no_eligible_media_after_filtering(
    state_store: StateStore,
) -> None:
    Config.cli_options["convert_to_jxl"] = True
    image = _touch(Config.output_folder / "photo.jpg")
    state_store.mark_failed(image, "metadata", "metadata failed")

    ConversionPhase(state_store).run()

    assert state_store.get_status(image, "conversion") == "skipped"


def test_conversion_phase_run_processes_enabled_image_and_video_conversions(
    monkeypatch: pytest.MonkeyPatch,
    state_store: StateStore,
) -> None:
    Config.cli_options["convert_to_jxl"] = True
    Config.cli_options["video_codec"] = "av1"
    image = _touch(Config.output_folder / "photo.jpg")
    video = _touch(Config.output_folder / "clip.mp4")
    unsupported = _touch(Config.output_folder / "notes.txt")
    jxl = Config.output_folder / "photo.jxl"
    av1 = Config.output_folder / "clip-av1.mp4"
    converted_videos: list[Path] = []

    class FakeJXLConverter:
        def __init__(self, input_path: Path) -> None:
            assert input_path == image

        def run(self) -> Path:
            jxl.write_bytes(b"jxl")
            return jxl

    class FakeVideoConverter:
        def __init__(self, file_path: Path) -> None:
            converted_videos.append(file_path)

        def run(self) -> Path:
            return av1

    monkeypatch.setattr(
        "src.conversion.conversion_phase.JXLConverter",
        FakeJXLConverter,
    )
    monkeypatch.setattr(
        "src.conversion.conversion_phase.VideoConverter",
        FakeVideoConverter,
    )

    ConversionPhase(state_store).run()

    assert converted_videos == [video]
    assert state_store.get_status(image, "conversion") == "done"
    assert state_store.get_status(jxl, "conversion") == "done"
    assert state_store.get_status(video, "conversion") == "done"
    assert state_store.get_status(av1, "conversion") == "done"
    assert state_store.get_status(unsupported, "conversion") == "skipped"


def test_conversion_phase_filters_blocked_and_resumable_media(
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    blocked = tmp_path / "blocked.jpg"
    done = tmp_path / "done.jpg"
    eligible = tmp_path / "eligible.jpg"
    state_store.mark_failed(blocked, "metadata", "metadata failed")
    state_store.mark_done(done, "conversion")
    phase = ConversionPhase(state_store)

    after_blocked = phase._filter_blocked_media([blocked, done, eligible])
    after_resumable = phase._filter_resumable_media(after_blocked)

    assert after_blocked == [done, eligible]
    assert after_resumable == [eligible]
    assert state_store.get_status(blocked, "conversion") == "skipped"


def test_conversion_phase_collect_results_marks_failed_file(
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "bad.jpg"
    future: Future[None] = Future()
    future.set_exception(RuntimeError("conversion broke"))

    ConversionPhase(state_store)._collect_results({future: file_path})

    assert state_store.get_status(file_path, "conversion") == "failed"


def test_conversion_phase_run_finishes_in_flight_work_on_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch,
    state_store: StateStore,
) -> None:
    Config.cli_options["convert_to_jxl"] = True
    image = _touch(Config.output_folder / "photo.jpg")
    handled: list[tuple[dict[object, object], str]] = []

    monkeypatch.setattr(
        ConversionPhase,
        "_submit_media",
        lambda _self, _executor, _media_files: {"future": image},
    )
    monkeypatch.setattr(
        ConversionPhase,
        "_collect_results",
        lambda _self, _futures: (_ for _ in ()).throw(KeyboardInterrupt),
    )
    monkeypatch.setattr(
        "src.conversion.conversion_phase.handle_phase_keyboard_interrupt",
        lambda futures, _collector, work_name: handled.append((futures, work_name)),
    )

    ConversionPhase(state_store).run()

    assert handled == [({"future": image}, "conversion")]


def test_app_run_orchestrates_phases_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    store = object()
    overlay_items = [Path("overlay-item.jpg")]
    output_items = [Path("output-item.jpg")]

    class FakeStateStore:
        def set_on_change(self, callback: object) -> None:
            calls.append(f"set_on_change:{callback.__name__}")

        def reset_running(self) -> None:
            calls.append("reset_running")

        def clear_skipped(self) -> None:
            calls.append("clear_skipped")

    class FakeUI:
        def __init__(self, state_store: object) -> None:
            assert isinstance(state_store, FakeStateStore)

        def refresh(self) -> None:
            calls.append("refresh")

        def set_phase(self, stage: str, items: list[Path]) -> None:
            calls.append(f"set_phase:{stage}:{len(items)}")

        def run(self, state: str, stage: str, items: list[Path]) -> None:
            calls.append(f"ui_run:{state}:{stage}:{len(items)}")

    class FakePhase:
        phase_name = "phase"

        def __init__(self, state_store: object) -> None:
            assert isinstance(state_store, FakeStateStore)

        def run(self) -> None:
            calls.append(f"run:{self.phase_name}")

    class FakeOverlayPhase(FakePhase):
        phase_name = "overlay"

    class FakeMetadataPhase(FakePhase):
        phase_name = "metadata"

    class FakeConversionPhase(FakePhase):
        phase_name = "conversion"

    monkeypatch.setattr("src.core.app.StateStore", FakeStateStore)
    monkeypatch.setattr("src.core.app.UpdateUI", FakeUI)
    monkeypatch.setattr("src.core.app.overlay_phase_items", lambda: overlay_items)
    monkeypatch.setattr("src.core.app.scan_output_files", lambda: output_items)
    monkeypatch.setattr("src.core.app.OverlayPhase", FakeOverlayPhase)
    monkeypatch.setattr("src.core.app.MetadataPhase", FakeMetadataPhase)
    monkeypatch.setattr("src.core.app.ConversionPhase", FakeConversionPhase)

    App().run()

    assert store is not None
    assert calls == [
        "set_on_change:refresh",
        "reset_running",
        "set_phase:overlay:1",
        "run:overlay",
        "set_phase:metadata:1",
        "run:metadata",
        "set_phase:conversion:1",
        "run:conversion",
        "ui_run:finished:conversion:1",
        "clear_skipped",
    ]


def test_app_run_smoke_processes_tiny_image_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    state_path: Path,
) -> None:
    Config.output_folder.mkdir()
    Config.memories_folder.mkdir()
    Config.json_path.write_text(
        (
            '{"Saved Media": [{"Date": "2024-01-01 08:00:00 UTC", '
            '"Location": "Latitude, Longitude: 60.1, 24.2"}]}'
        ),
        encoding="utf-8",
    )
    main = Config.memories_folder / "2024-01-01_001-main.jpg"
    overlay = Config.memories_folder / "2024-01-01_001-overlay.png"
    Image.new("RGB", (2, 2), (0, 0, 0)).save(main, format="JPEG")
    Image.new("RGBA", (2, 2), (0, 255, 0, 255)).save(overlay, format="PNG")
    Config.cli_options.update(
        {
            "convert_to_jxl": False,
            "overlay_mode": "on",
            "write_metadata": True,
            "jpeg_quality": 100,
        }
    )

    class QuietDisplay:
        def __init__(self, *_args: object) -> None:
            pass

        def print_display(self, _state: str | None = None) -> None:
            pass

    monkeypatch.setattr(
        "src.core.state_store.state_store.default_state_path",
        lambda: state_path,
    )
    monkeypatch.setattr("src.ui.update_ui.Display", QuietDisplay)

    App().run()

    output = Config.output_folder / "2024-01-01_001-overlaid.jpg"
    assert output.exists()
    assert piexif.load(str(output))["GPS"][piexif.GPSIFD.GPSLatitudeRef] == b"N"
