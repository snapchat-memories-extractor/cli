from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from src.config import Config
from src.metadata.json_memory_loader import (
    Memory,
    _parse_datetime,
    _parse_location,
    load_json_memories,
)
from src.metadata.media_datetime_reader import MediaDatetimeReader
from src.metadata.memory_path_matcher import match_memory_paths
from src.metadata.metadata_phase import MetadataPhase

if TYPE_CHECKING:
    import pytest

    from src.core.state_store import StateStore


def _write_memories_json(items: list[dict[str, object]]) -> None:
    Config.json_path.write_text(
        json.dumps({"Saved Media": items}),
        encoding="utf-8",
    )


def _memory(
    timestamp: datetime,
    coords: tuple[float, float] | None = None,
) -> Memory:
    return Memory(captured_at=timestamp, location_coords=coords)


def test_load_json_memories_parses_dates_and_coordinates() -> None:
    _write_memories_json(
        [
            {
                "Date": "2024-01-02 03:04:05 UTC",
                "Location": "Latitude, Longitude: 60.123, 24.456",
            },
            {
                "Date": "2024-01-03T01:02:03 UTC",
                "Location": "Latitude, Longitude: 0.0, 0.0",
            },
            {"Date": "2024-01-04T05:06:07 UTC", "Location": "not coordinates"},
            {
                "Date": "not-a-date",
                "Location": "Latitude, Longitude: 10.0, 20.0",
            },
        ]
    )

    memories = load_json_memories()

    assert len(memories) == 3
    assert memories[0].captured_at == datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    assert memories[0].location_coords == (60.123, 24.456)
    assert memories[1].location_coords is None
    assert memories[2].location_coords is None


def test_load_json_memories_handles_missing_saved_media_list() -> None:
    Config.json_path.write_text("{}", encoding="utf-8")

    assert load_json_memories() == []


def test_parse_location_handles_objects_that_cannot_be_split() -> None:
    class OddLocation:
        def replace(self, _prefix: str, _replacement: str) -> object:
            return object()

    assert _parse_location({"Location": OddLocation()}) is None


def test_parse_datetime_ignores_non_string_dates() -> None:
    assert _parse_datetime({"Date": 123}) is None


def test_load_json_memories_logs_missing_location_as_error_in_strict_mode(
    caplog: pytest.LogCaptureFixture,
) -> None:
    Config.cli_options["strict_location"] = True
    _write_memories_json([{"Date": "2024-01-02 03:04:05 UTC"}])

    load_json_memories()

    assert "Skipped JSON memory with no usable location" in caplog.text
    assert any(record.levelname == "ERROR" for record in caplog.records)


def test_match_memory_paths_assigns_files_by_date_and_modified_time(
    tmp_path: Path,
) -> None:
    early_file = tmp_path / "2024-02-03-early.jpg"
    late_file = tmp_path / "2024-02-03-late.jpg"
    early_file.write_bytes(b"early")
    late_file.write_bytes(b"late")
    os.utime(early_file, (100, 100))
    os.utime(late_file, (200, 200))
    early_memory = _memory(datetime(2024, 2, 3, 8, 0, tzinfo=UTC))
    late_memory = _memory(datetime(2024, 2, 3, 9, 0, tzinfo=UTC))

    matched, unmatched = match_memory_paths(
        [late_file, early_file],
        [late_memory, early_memory],
    )

    assert unmatched == []
    assert matched == [early_memory, late_memory]
    assert early_memory.file_path == early_file
    assert late_memory.file_path == late_file


def test_match_memory_paths_marks_whole_day_unmatched_when_counts_differ(
    tmp_path: Path,
) -> None:
    first = tmp_path / "2024-02-03-first.jpg"
    second = tmp_path / "2024-02-03-second.jpg"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    matched, unmatched = match_memory_paths(
        [first, second],
        [_memory(datetime(2024, 2, 3, 8, 0, tzinfo=UTC))],
    )

    assert matched == []
    assert unmatched == [first, second]


def test_match_memory_paths_returns_invalid_filename_dates_as_unmatched(
    tmp_path: Path,
) -> None:
    invalid = tmp_path / "memory-without-date.jpg"
    invalid.write_bytes(b"image")

    matched, unmatched = match_memory_paths(
        [invalid],
        [_memory(datetime(2024, 2, 3, 8, 0, tzinfo=UTC))],
    )

    assert matched == []
    assert unmatched == [invalid]


def test_match_memory_paths_handles_file_stat_errors(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    media = tmp_path / "2024-02-03-main.jpg"
    media.write_bytes(b"image")
    monkeypatch.setattr(Path, "stat", lambda _self: (_ for _ in ()).throw(OSError))

    matched, unmatched = match_memory_paths(
        [media],
        [_memory(datetime(2024, 2, 3, 8, 0, tzinfo=UTC))],
    )

    assert matched == []
    assert unmatched == [media]


def test_media_datetime_reader_reads_image_modified_time_as_utc(
    tmp_path: Path,
) -> None:
    image = tmp_path / "photo.jpg"
    image.write_bytes(b"image")
    os.utime(image, (1_700_000_000, 1_700_000_000))

    captured_at = MediaDatetimeReader(image).run()

    assert captured_at == datetime.fromtimestamp(1_700_000_000, tz=UTC)


def test_media_datetime_reader_returns_none_for_missing_image(
    tmp_path: Path,
) -> None:
    assert MediaDatetimeReader(tmp_path / "missing.jpg").run() is None


def test_media_datetime_reader_extracts_and_parses_video_creation_time() -> None:
    raw_output = """
      Metadata:
        major_brand     : mp42
        creation_time   : 2024-05-01T12:30:45+02:00
    """

    raw_value = MediaDatetimeReader._extract_creation_time(raw_output)
    parsed = MediaDatetimeReader._parse_video_datetime(raw_value)

    assert raw_value == "2024-05-01T12:30:45+02:00"
    assert parsed == datetime(2024, 5, 1, 10, 30, 45, tzinfo=UTC)


def test_media_datetime_reader_returns_none_for_invalid_video_datetime() -> None:
    assert MediaDatetimeReader._extract_creation_time("no metadata") is None
    assert MediaDatetimeReader._parse_video_datetime("invalid") is None


def test_metadata_phase_strict_location_deletes_unlocated_file(
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    Config.cli_options["strict_location"] = True
    file_path = tmp_path / "2024-01-01-main.jpg"
    file_path.write_bytes(b"image")
    memory = Memory(
        captured_at=datetime(2024, 1, 1, tzinfo=UTC),
        location_coords=None,
        file_path=file_path,
    )

    result = MetadataPhase(state_store)._apply_metadata(memory, file_path)

    assert result is False
    assert not file_path.exists()
    assert state_store.get_status(file_path, "metadata") == "skipped"


def test_metadata_phase_dispatches_image_and_video_writers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    class FakeImageWriter:
        def __init__(self, _memory: Memory) -> None:
            pass

        def run(self) -> None:
            calls.append("image")

    class FakeVideoWriter:
        def __init__(self, _memory: Memory) -> None:
            pass

        def run(self) -> None:
            calls.append("video")

    monkeypatch.setattr(
        "src.metadata.metadata_phase.ImageMetadataWriter",
        FakeImageWriter,
    )
    monkeypatch.setattr(
        "src.metadata.metadata_phase.VideoMetadataWriter",
        FakeVideoWriter,
    )
    memory = Memory(
        captured_at=datetime(2024, 1, 1, tzinfo=UTC),
        location_coords=(1.0, 2.0),
    )

    MetadataPhase._write_metadata(memory, tmp_path / "photo.JPG")
    MetadataPhase._write_metadata(memory, tmp_path / "video.mp4")

    assert calls == ["image", "video"]


def test_metadata_phase_filters_unsupported_media(
    state_store: StateStore,
    tmp_path: Path,
) -> None:
    image = tmp_path / "photo.jpg"
    video = tmp_path / "video.mp4"
    notes = tmp_path / "notes.txt"

    eligible = MetadataPhase(state_store)._filter_supported_media([image, notes, video])

    assert eligible == [image, video]
    assert state_store.get_status(notes, "metadata") == "skipped"
