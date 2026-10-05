from collections.abc import Callable, Iterable
from pathlib import Path
from threading import RLock
from typing import cast

from src.core.state_store.persistence import (
    default_state_path,
    delete_state_file,
    empty_state,
    load_state,
    save_state,
)
from src.core.state_store.schema import (
    RETRYABLE_STATUSES,
    TERMINAL_STATUSES,
    VALID_STAGES,
    VALID_STATUSES,
    PipelineStage,
    PipelineStatus,
    StageProgress,
    StageState,
)
from src.core.state_store.state_data import (
    current_timestamp,
    read_stage_state,
    remove_skipped_stages,
    reset_stage_statuses,
    stage_state_payload,
    stage_states,
    stages_for_item,
)
from src.logger import log


class StateStore:
    def __init__(self, on_change: Callable[[], None] | None = None) -> None:
        self.path = default_state_path()
        self._lock = RLock()
        self._state = load_state(self.path)
        self._on_change = on_change

    def set_on_change(self, on_change: Callable[[], None] | None) -> None:
        self._on_change = on_change

    def get_status(self, item: Path, stage: PipelineStage) -> PipelineStatus:
        stage = self._normalize_stage(stage)
        if stage is None:
            return "pending"

        key = self._item_key(item)

        with self._lock:
            return read_stage_state(self._files_locked(), key, stage).status

    def summarize_stage(
        self,
        items: Iterable[Path],
        stage: PipelineStage,
    ) -> StageProgress:
        stage = self._normalize_stage(stage)
        if stage is None:
            return StageProgress("overlay", 0)

        item_keys = {self._item_key(item) for item in items}

        with self._lock:
            files = self._files_locked()
            statuses = [
                read_stage_state(files, item_key, stage).status
                for item_key in item_keys
            ]

        counts = dict.fromkeys(VALID_STATUSES, 0)
        for status in statuses:
            counts[status] += 1

        return StageProgress(
            stage=stage,
            total=len(item_keys),
            pending=counts["pending"],
            running=counts["running"],
            done=counts["done"],
            failed=counts["failed"],
            skipped=counts["skipped"],
        )

    def have_stage_failed(
        self,
        item: Path,
        stages: tuple[PipelineStage, ...],
    ) -> PipelineStage | None:
        failed_stage = None
        for stage in stages:
            if self.get_status(item, stage) == "failed":
                failed_stage = stage
        return failed_stage

    def terminal_status(
        self,
        item: Path,
        stage: PipelineStage,
    ) -> PipelineStatus | None:
        status = self.get_status(item, stage)
        if status in TERMINAL_STATUSES:
            return status
        return None

    def reset_running(self) -> None:
        reset_count = self._reset_statuses(("running",))
        if reset_count:
            log(
                f"Reset {reset_count} stale running pipeline state(s) to pending.",
                "warning",
            )

    def reset_retryable(self) -> None:
        reset_count = self._reset_statuses(RETRYABLE_STATUSES)
        if reset_count:
            log(
                f"Reset {reset_count} failed pipeline state(s) to pending.",
                "info",
            )

    def clear_skipped(self) -> None:
        clear_count = 0
        removed_empty_files = False

        with self._lock:
            files = self._files_locked()
            for key, item_state in list(files.items()):
                stages = stage_states(item_state)
                if stages is None:
                    continue

                clear_count += remove_skipped_stages(stages)
                if not stages:
                    files.pop(key, None)
                    removed_empty_files = True

            if clear_count or removed_empty_files:
                self._save_locked()

        if clear_count:
            log(f"Cleared {clear_count} skipped pipeline state(s).", "info")

    def mark_running(self, item: Path, stage: PipelineStage) -> StageState:
        return self._write_stage_state(
            item,
            stage,
            "running",
            increment_attempts=True,
            last_error=None,
        )

    def mark_done(
        self,
        item: Path,
        stage: PipelineStage,
    ) -> StageState:
        return self._write_stage_state(
            item,
            stage,
            "done",
            last_error=None,
        )

    def mark_skipped(self, item: Path, stage: PipelineStage) -> StageState:
        stage = self._normalize_stage(stage)
        if stage is None:
            return StageState()

        key = self._item_key(item)

        with self._lock:
            files = self._files_locked()
            current = read_stage_state(files, key, stage)
            if current.status in ("done", "failed"):
                return current

            updated = self._write_stage_state_locked(
                files,
                key,
                stage,
                "skipped",
                increment_attempts=False,
                last_error=None,
            )

        self._notify_change()
        return updated

    def mark_failed(
        self,
        item: Path,
        stage: PipelineStage,
        error: str,
    ) -> StageState:
        stage = self._normalize_stage(stage)
        if stage is None:
            return StageState()

        key = self._item_key(item)

        with self._lock:
            files = self._files_locked()
            current = read_stage_state(files, key, stage)
            updated = self._write_stage_state_locked(
                files,
                key,
                stage,
                "failed",
                increment_attempts=current.status != "running",
                last_error=error,
            )

        self._notify_change()
        return updated

    def delete(self) -> None:
        delete_state_file(self.path)
        with self._lock:
            self._state = empty_state()
        self._notify_change()

    def _write_stage_state(
        self,
        item: Path,
        stage: PipelineStage,
        status: PipelineStatus,
        *,
        increment_attempts: bool = False,
        last_error: str | None,
    ) -> StageState:
        stage = self._normalize_stage(stage)
        status = self._normalize_status(status)
        if stage is None or status is None:
            return StageState()

        key = self._item_key(item)

        with self._lock:
            updated = self._write_stage_state_locked(
                self._files_locked(),
                key,
                stage,
                status,
                increment_attempts=increment_attempts,
                last_error=last_error,
            )
        self._notify_change()
        return updated

    def _write_stage_state_locked(
        self,
        files: dict[str, object],
        key: str,
        stage: PipelineStage,
        status: PipelineStatus,
        *,
        increment_attempts: bool,
        last_error: str | None,
    ) -> StageState:
        current = read_stage_state(files, key, stage)
        attempts = current.attempts + 1 if increment_attempts else current.attempts
        updated = StageState(
            status=status,
            attempts=attempts,
            last_error=last_error,
            updated_at=current_timestamp(),
        )

        stages = stages_for_item(files, key)
        stages[stage] = stage_state_payload(updated)
        self._save_locked()
        return updated

    def _reset_statuses(self, statuses: tuple[PipelineStatus, ...]) -> int:
        reset_count = 0
        with self._lock:
            for item_state in self._files_locked().values():
                reset_count += reset_stage_statuses(item_state, statuses)

            if reset_count:
                self._save_locked()

        return reset_count

    def _files_locked(self) -> dict[str, object]:
        files = self._state.get("files")
        if isinstance(files, dict):
            return files

        log(
            f"Pipeline state had invalid in-memory data, resetting: {self.path}",
            "warning",
        )
        self._state = empty_state()
        return cast("dict[str, object]", self._state["files"])

    def _save_locked(self) -> None:
        save_state(self.path, self._state)

    def _notify_change(self) -> None:
        if self._on_change is None:
            return

        try:
            self._on_change()
        except Exception as error:
            log(f"Pipeline state change callback failed: {error}", "warning")

    @staticmethod
    def _normalize_stage(stage: PipelineStage) -> PipelineStage | None:
        if stage not in VALID_STAGES:
            log(f"Unknown pipeline stage ignored: {stage}", "warning")
            return None
        return cast("PipelineStage", stage)

    @staticmethod
    def _normalize_status(status: PipelineStatus) -> PipelineStatus | None:
        if status not in VALID_STATUSES:
            log(f"Unknown pipeline status ignored: {status}", "warning")
            return None
        return cast("PipelineStatus", status)

    @staticmethod
    def _item_key(item: Path) -> str:
        return item.name
