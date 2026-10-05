from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from src.config import Config
from src.config.defaults import APP_STATE_DIR, PIPELINE_STATE_FILE_PREFIX
from src.core.state_store.persistence import (
    default_state_path,
    delete_state_file,
    empty_state,
    load_state,
    save_state,
)
from src.core.state_store.state_data import (
    read_stage_state,
    reset_stage_statuses,
    stages_for_item,
)

if TYPE_CHECKING:
    from src.core.state_store.state_store import StateStore


def test_default_state_path_is_keyed_by_memories_folder(tmp_path: Path) -> None:
    Config.cli_options["memories_folder"] = str(tmp_path / "memories")
    source_path = os.path.normcase(str((tmp_path / "memories").absolute()))
    source_key = hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:16]

    path = default_state_path()

    assert path.parent.name == APP_STATE_DIR
    assert path.name == f"{PIPELINE_STATE_FILE_PREFIX}-{source_key}.json"


def test_empty_state_returns_fresh_file_mapping() -> None:
    first = empty_state()
    second = empty_state()
    first["files"]["photo.jpg"] = {}

    assert second == {"files": {}}


def test_load_state_returns_valid_file_mapping(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text('{"files": {"photo.jpg": {"stages": {}}}}', encoding="utf-8")

    assert load_state(path) == {"files": {"photo.jpg": {"stages": {}}}}


@pytest.mark.parametrize("content", ["not json", "[]", '{"files": []}'])
def test_load_state_returns_empty_state_for_invalid_files(
    tmp_path: Path,
    content: str,
) -> None:
    path = tmp_path / "state.json"
    path.write_text(content, encoding="utf-8")

    assert load_state(path) == {"files": {}}


def test_load_state_returns_empty_state_when_read_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.json"
    path.write_text("{}", encoding="utf-8")

    def fail_read_text(self: Path, *_args: object, **_kwargs: object) -> str:
        if self == path:
            raise OSError("locked")
        return ""

    monkeypatch.setattr(Path, "read_text", fail_read_text)

    assert load_state(path) == {"files": {}}


def test_save_state_writes_pretty_json_atomically(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    state = {"files": {"photo.jpg": {"stages": {"overlay": {"status": "done"}}}}}

    save_state(path, state)

    assert json.loads(path.read_text(encoding="utf-8")) == state
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert not (tmp_path / "state.json.tmp").exists()


def test_save_state_swallows_unserializable_state(tmp_path: Path) -> None:
    path = tmp_path / "state.json"

    save_state(path, {"files": {"bad": object()}})

    assert not path.exists()


def test_delete_state_file_removes_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{}", encoding="utf-8")

    delete_state_file(path)

    assert not path.exists()


def test_delete_state_file_handles_missing_file(tmp_path: Path) -> None:
    delete_state_file(tmp_path / "missing.json")


def test_delete_state_file_logs_when_delete_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "state.json"
    path.write_text("{}", encoding="utf-8")

    def fail_unlink(self: Path) -> None:
        if self == path:
            raise OSError("locked")
        self.unlink()

    monkeypatch.setattr(Path, "unlink", fail_unlink)

    delete_state_file(path)

    assert path.exists()


def test_read_stage_state_sanitizes_invalid_payload() -> None:
    state = {
        "photo.jpg": {
            "stages": {
                "overlay": {
                    "status": "surprise",
                    "attempts": "many",
                    "last_error": 404,
                    "updated_at": [],
                }
            }
        }
    }

    stage_state = read_stage_state(state, "photo.jpg", "overlay")

    assert stage_state.status == "pending"
    assert stage_state.attempts == 0
    assert stage_state.last_error is None
    assert stage_state.updated_at is None


def test_stages_for_item_replaces_invalid_item_and_stage_shapes() -> None:
    files: dict[str, object] = {"photo.jpg": "invalid"}

    stages = stages_for_item(files, "photo.jpg")
    stages["overlay"] = {"status": "done"}

    assert files == {
        "photo.jpg": {
            "stages": {
                "overlay": {"status": "done"},
            }
        }
    }


def test_reset_stage_statuses_only_resets_requested_statuses() -> None:
    item_state = {
        "stages": {
            "overlay": {"status": "running", "last_error": "old"},
            "metadata": {"status": "failed", "last_error": "bad"},
            "conversion": {"status": "done", "last_error": None},
        }
    }

    reset_count = reset_stage_statuses(item_state, ("running", "failed"))

    assert reset_count == 2
    assert item_state["stages"]["overlay"]["status"] == "pending"
    assert item_state["stages"]["metadata"]["status"] == "pending"
    assert item_state["stages"]["conversion"]["status"] == "done"


def test_reset_stage_statuses_ignores_items_without_stage_mapping() -> None:
    assert reset_stage_statuses("invalid", ("failed",)) == 0
    assert reset_stage_statuses({"stages": []}, ("failed",)) == 0


def test_state_store_on_change_runs_for_successful_write(
    state_store: StateStore,
) -> None:
    calls: list[str] = []
    state_store.set_on_change(lambda: calls.append("changed"))

    state_store.mark_done(Path("photo.jpg"), "overlay")

    assert calls == ["changed"]


def test_state_store_on_change_failure_is_swallowed(state_store: StateStore) -> None:
    def fail() -> None:
        error_message = "ui failed"
        raise RuntimeError(error_message)

    state_store.set_on_change(fail)

    state_store.mark_done(Path("photo.jpg"), "overlay")

    assert state_store.get_status(Path("photo.jpg"), "overlay") == "done"


def test_state_store_delete_resets_memory_and_removes_state_file(
    state_store: StateStore,
) -> None:
    calls: list[str] = []
    state_store.set_on_change(lambda: calls.append("changed"))
    state_store.mark_done(Path("photo.jpg"), "overlay")

    state_store.delete()

    assert calls == ["changed", "changed"]
    assert state_store.get_status(Path("photo.jpg"), "overlay") == "pending"
    assert not state_store.path.exists()


def test_state_store_clear_skipped_removes_empty_file_entry(
    state_store: StateStore,
) -> None:
    item = Path("only-skipped.jpg")
    state_store.mark_skipped(item, "overlay")

    state_store.clear_skipped()

    assert state_store._state == {"files": {}}


def test_state_store_clear_skipped_ignores_items_without_stage_mapping(
    state_store: StateStore,
) -> None:
    state_store._state["files"] = {"bad": "invalid"}

    state_store.clear_skipped()

    assert state_store._state == {"files": {"bad": "invalid"}}


def test_state_store_invalid_status_write_is_ignored(state_store: StateStore) -> None:
    state = state_store._write_stage_state(
        Path("photo.jpg"),
        "overlay",
        "surprise",
        last_error=None,
    )

    assert state.status == "pending"
    assert state_store.get_status(Path("photo.jpg"), "overlay") == "pending"


def test_state_store_recovers_invalid_in_memory_files_shape(
    state_store: StateStore,
) -> None:
    state_store._state["files"] = []

    assert state_store.get_status(Path("photo.jpg"), "overlay") == "pending"
    assert state_store._state == {"files": {}}
