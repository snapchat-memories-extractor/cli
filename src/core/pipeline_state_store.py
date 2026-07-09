import hashlib
import json
import os
from contextlib import suppress
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Literal, TypeAlias, cast

from src.config import Config
from src.logger import log

APP_STATE_DIR = ".snapchat-memories"
PIPELINE_STATE_FILE_PREFIX = "pipeline-state"

PipelineStage: TypeAlias = Literal["overlay", "metadata", "conversion"]
PipelineStatus: TypeAlias = Literal["pending", "running", "done", "failed", "skipped"]

VALID_STAGES: tuple[PipelineStage, ...] = ("overlay", "metadata", "conversion")
VALID_STATUSES: tuple[PipelineStatus, ...] = (
    "pending",
    "running",
    "done",
    "failed",
    "skipped",
)


@dataclass(frozen=True)
class StageState:
    status: PipelineStatus = "pending"
    attempts: int = 0
    last_error: str | None = None
    updated_at: str | None = None


class PipelineStateStore:
    def __init__(self) -> None:
        self.path = self._default_path()
        self._lock = RLock()
        self._state = self._load()

    def get_stage_state(
        self,
        item: str | Path,
        stage: PipelineStage,
    ) -> StageState:
        stage = self._normalize_stage(stage)
        if stage is None:
            return StageState()

        key = self._item_key(item)

        with self._lock:
            return self._read_stage_state_locked(key, stage)

    def get_status(self, item: str | Path, stage: PipelineStage) -> PipelineStatus:
        return self.get_stage_state(item, stage).status

    def has_failed(
        self,
        item: str | Path,
        stages: tuple[PipelineStage, ...],
    ) -> bool:
        return any(self.get_status(item, stage) == "failed" for stage in stages)

    def has_failures(self) -> bool:
        with self._lock:
            return any(
                self._item_has_failed(item_state)
                for item_state in self._files_locked().values()
            )

    def mark_running(self, item: str | Path, stage: PipelineStage) -> StageState:
        return self._write_stage_state(
            item,
            stage,
            "running",
            increment_attempts=True,
            last_error=None,
        )

    def mark_done(self, item: str | Path, stage: PipelineStage) -> StageState:
        return self._write_stage_state(item, stage, "done", last_error=None)

    def mark_skipped(self, item: str | Path, stage: PipelineStage) -> StageState:
        return self._write_stage_state(item, stage, "skipped", last_error=None)

    def mark_failed(
        self,
        item: str | Path,
        stage: PipelineStage,
        error: str,
    ) -> StageState:
        stage = self._normalize_stage(stage)
        if stage is None:
            return StageState()

        key = self._item_key(item)

        with self._lock:
            current = self._read_stage_state_locked(key, stage)
            return self._write_stage_state_locked(
                key,
                stage,
                "failed",
                increment_attempts=current.status != "running",
                last_error=error,
            )

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return deepcopy(self._state)

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
        item: str | Path,
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
            status=cast(PipelineStatus, status),
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
        return cast(dict[str, object], self._state["files"])

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
    def _item_key(item: str | Path) -> str:
        if isinstance(item, Path):
            return item.name
        return item

    @staticmethod
    def _normalize_stage(stage: PipelineStage) -> PipelineStage | None:
        if stage not in VALID_STAGES:
            log(f"Unknown pipeline stage ignored: {stage}", "warning")
            return None
        return cast(PipelineStage, stage)

    @staticmethod
    def _normalize_status(status: PipelineStatus) -> PipelineStatus | None:
        if status not in VALID_STATUSES:
            log(f"Unknown pipeline status ignored: {status}", "warning")
            return None
        return cast(PipelineStatus, status)

    @staticmethod
    def _item_has_failed(item_state: object) -> bool:
        if not isinstance(item_state, dict):
            return False

        stages = item_state.get("stages")
        if not isinstance(stages, dict):
            return False

        return any(
            isinstance(stage_state, dict) and stage_state.get("status") == "failed"
            for stage_state in stages.values()
        )

    @staticmethod
    def _now() -> str:
        return datetime.now(tz=timezone.utc).isoformat()

    @staticmethod
    def _default_path() -> Path:
        return PipelineStateStore._repo_state_dir() / (
            f"{PIPELINE_STATE_FILE_PREFIX}-"
            f"{PipelineStateStore._source_folder_key()}.json"
        )

    @staticmethod
    def _repo_state_dir() -> Path:
        return Path(__file__).resolve().parents[2] / APP_STATE_DIR

    @staticmethod
    def _source_folder_key() -> str:
        source_folder = Config.memories_folder or Path("data/memories")
        source_path = os.path.normcase(str(source_folder.expanduser().absolute()))
        return hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:16]
