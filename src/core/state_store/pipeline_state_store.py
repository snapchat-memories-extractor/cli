import hashlib
import json
import os
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import cast

from src.config import Config
from src.config.defaults import APP_STATE_DIR, PIPELINE_STATE_FILE_PREFIX
from src.core.state_store.schema import (
    RETRYABLE_STATUSES,
    TERMINAL_STATUSES,
    VALID_STAGES,
    VALID_STATUSES,
    PipelineStage,
    PipelineStatus,
    StageState,
)
from src.logger import log


class PipelineStateStore:
    def __init__(self) -> None:
        self.path = self._default_path()
        self._lock = RLock()
        self._state = self._load()

    def get_status(self, item: Path, stage: PipelineStage) -> PipelineStatus:
        stage = self._normalize_stage(stage)
        if stage is None:
            return "pending"

        key = item.name

        with self._lock:
            return self._read_stage_state_locked(key, stage).status

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
        reset_count = 0
        with self._lock:
            for item_state in self._files_locked().values():
                reset_count += self._reset_item_running_states(item_state)

            if reset_count:
                self._save_locked()

        if reset_count:
            log(
                f"Reset {reset_count} stale running pipeline state(s) to pending.",
                "warning",
            )

    def reset_retryable(self) -> None:
        reset_count = 0
        with self._lock:
            for item_state in self._files_locked().values():
                reset_count += self._reset_item_retryable_states(item_state)

            if reset_count:
                self._save_locked()

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
                stages = self._stage_states(item_state)
                if stages is not None:
                    clear_count += self._remove_skipped_stages(stages)

                if stages == {}:
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

        key = item.name

        with self._lock:
            current = self._read_stage_state_locked(key, stage)
            if current.status in ("done", "failed"):
                return current

            return self._write_stage_state_locked(
                key,
                stage,
                "skipped",
                increment_attempts=False,
                last_error=None,
            )

    def mark_failed(
        self,
        item: Path,
        stage: PipelineStage,
        error: str,
    ) -> StageState:
        stage = self._normalize_stage(stage)
        if stage is None:
            return StageState()

        key = item.name

        with self._lock:
            current = self._read_stage_state_locked(key, stage)
            return self._write_stage_state_locked(
                key,
                stage,
                "failed",
                increment_attempts=current.status != "running",
                last_error=error,
            )

    def delete(self) -> None:
        deleted = False
        if self.path.exists():
            with suppress(OSError):
                self.path.unlink()
                deleted = True

            if deleted:
                log(f"Deleted pipeline state file: {self.path}", "info")
            else:
                log(f"Could not delete pipeline state file: {self.path}", "warning")

        with self._lock:
            self._state = self._empty_state()

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

        key = item.name

        with self._lock:
            return self._write_stage_state_locked(
                key,
                stage,
                status,
                increment_attempts=increment_attempts,
                last_error=last_error,
            )

    def _write_stage_state_locked(
        self,
        key: str,
        stage: PipelineStage,
        status: PipelineStatus,
        *,
        increment_attempts: bool,
        last_error: str | None,
    ) -> StageState:
        current = self._read_stage_state_locked(key, stage)
        attempts = current.attempts + 1 if increment_attempts else current.attempts
        updated = StageState(
            status=status,
            attempts=attempts,
            last_error=last_error,
            updated_at=self._now(),
        )

        stages = self._stages_for_locked(key)
        stages[stage] = {
            "status": updated.status,
            "attempts": updated.attempts,
            "last_error": updated.last_error,
            "updated_at": updated.updated_at,
        }
        self._save_locked()
        return updated

    def _read_stage_state_locked(
        self,
        key: str,
        stage: PipelineStage,
    ) -> StageState:
        files = self._files_locked()
        item_state = files.get(key)
        if not isinstance(item_state, dict):
            return StageState()

        stages = item_state.get("stages")
        if not isinstance(stages, dict):
            return StageState()

        stage_state = stages.get(stage)
        if not isinstance(stage_state, dict):
            return StageState()

        status = stage_state.get("status", "pending")
        attempts = stage_state.get("attempts", 0)
        last_error = stage_state.get("last_error")
        updated_at = stage_state.get("updated_at")

        if status not in VALID_STATUSES:
            status = "pending"
        if not isinstance(attempts, int):
            attempts = 0
        if not isinstance(last_error, str):
            last_error = None
        if not isinstance(updated_at, str):
            updated_at = None

        return StageState(
            status=cast("PipelineStatus", status),
            attempts=attempts,
            last_error=last_error,
            updated_at=updated_at,
        )

    def _stages_for_locked(self, key: str) -> dict[str, object]:
        files = self._files_locked()
        item_state = files.setdefault(key, {"stages": {}})
        if not isinstance(item_state, dict):
            item_state = {"stages": {}}
            files[key] = item_state

        stages = item_state.setdefault("stages", {})
        if not isinstance(stages, dict):
            stages = {}
            item_state["stages"] = stages

        return stages

    def _files_locked(self) -> dict[str, object]:
        files = self._state.get("files")
        if isinstance(files, dict):
            return files

        log(
            f"Pipeline state had invalid in-memory data, resetting: {self.path}",
            "warning",
        )
        self._state = self._empty_state()
        return cast("dict[str, object]", self._state["files"])

    def _load(self) -> dict[str, object]:
        if not self.path.exists():
            return self._empty_state()

        raw_text = None
        with suppress(OSError):
            raw_text = self.path.read_text(encoding="utf-8")

        if raw_text is None:
            log(
                f"Could not read pipeline state file, starting fresh: {self.path}",
                "warning",
            )
            return self._empty_state()

        raw_state = None
        with suppress(json.JSONDecodeError):
            raw_state = json.loads(raw_text)

        if not isinstance(raw_state, dict):
            log(
                f"Could not parse pipeline state file, starting fresh: {self.path}",
                "warning",
            )
            return self._empty_state()

        files = raw_state.get("files")
        if not isinstance(files, dict):
            log(
                f"Pipeline state file had invalid shape, starting fresh: {self.path}",
                "warning",
            )
            return self._empty_state()

        return {"files": files}

    def _save_locked(self) -> None:
        temp_path = self.path.with_name(f"{self.path.name}.tmp")
        saved = False

        with suppress(OSError, TypeError):
            self.path.parent.mkdir(parents=True, exist_ok=True)
            serialized = json.dumps(self._state, indent=2, sort_keys=True)
            temp_path.write_text(f"{serialized}\n", encoding="utf-8")
            temp_path.replace(self.path)
            saved = True

        if not saved:
            log(f"Could not save pipeline state file: {self.path}", "warning")

    @staticmethod
    def _empty_state() -> dict[str, object]:
        return {"files": {}}

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
    def _reset_item_running_states(item_state: object) -> int:
        if not isinstance(item_state, dict):
            return 0

        stages = item_state.get("stages")
        if not isinstance(stages, dict):
            return 0

        reset_count = 0
        for stage_state in stages.values():
            if isinstance(stage_state, dict) and stage_state.get("status") == "running":
                stage_state["status"] = "pending"
                stage_state["last_error"] = None
                stage_state["updated_at"] = PipelineStateStore._now()
                reset_count += 1

        return reset_count

    @staticmethod
    def _reset_item_retryable_states(item_state: object) -> int:
        if not isinstance(item_state, dict):
            return 0

        stages = item_state.get("stages")
        if not isinstance(stages, dict):
            return 0

        reset_count = 0
        for stage_state in stages.values():
            if (
                isinstance(stage_state, dict)
                and stage_state.get("status") in RETRYABLE_STATUSES
            ):
                stage_state["status"] = "pending"
                stage_state["last_error"] = None
                stage_state["updated_at"] = PipelineStateStore._now()
                reset_count += 1

        return reset_count

    @staticmethod
    def _stage_states(item_state: object) -> dict[str, object] | None:
        if not isinstance(item_state, dict):
            return None

        stages = item_state.get("stages")
        if isinstance(stages, dict):
            return stages

        return None

    @staticmethod
    def _remove_skipped_stages(stages: dict[str, object]) -> int:
        skipped_stages = [
            stage
            for stage, stage_state in stages.items()
            if isinstance(stage_state, dict)
            and stage_state.get("status") == "skipped"
        ]

        for stage in skipped_stages:
            stages.pop(stage, None)

        return len(skipped_stages)

    @staticmethod
    def _now() -> str:
        return datetime.now(tz=UTC).isoformat()

    @staticmethod
    def _default_path() -> Path:
        source_folder = Config.memories_folder or Path("data/memories")
        source_path = os.path.normcase(str(source_folder.expanduser().absolute()))
        source_key = hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:16]
        state_dir = Path(__file__).resolve().parents[3] / APP_STATE_DIR

        return state_dir / f"{PIPELINE_STATE_FILE_PREFIX}-{source_key}.json"
