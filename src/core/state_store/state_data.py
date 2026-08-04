from datetime import UTC, datetime
from typing import cast

from src.core.state_store.schema import (
    VALID_STATUSES,
    PipelineStage,
    PipelineStatus,
    StageState,
)


def read_stage_state(
    files: dict[str, object],
    key: str,
    stage: PipelineStage,
) -> StageState:
    stages = stage_states(files.get(key))
    if stages is None:
        return StageState()

    raw_stage_state = stages.get(stage)
    if not isinstance(raw_stage_state, dict):
        return StageState()

    status = raw_stage_state.get("status", "pending")
    attempts = raw_stage_state.get("attempts", 0)
    last_error = raw_stage_state.get("last_error")
    updated_at = raw_stage_state.get("updated_at")

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


def stages_for_item(files: dict[str, object], key: str) -> dict[str, object]:
    item_state = files.setdefault(key, {"stages": {}})
    if not isinstance(item_state, dict):
        item_state = {"stages": {}}
        files[key] = item_state

    stages = item_state.setdefault("stages", {})
    if not isinstance(stages, dict):
        stages = {}
        item_state["stages"] = stages

    return stages


def stage_state_payload(stage_state: StageState) -> dict[str, object]:
    return {
        "status": stage_state.status,
        "attempts": stage_state.attempts,
        "last_error": stage_state.last_error,
        "updated_at": stage_state.updated_at,
    }


def reset_stage_statuses(
    item_state: object,
    statuses: tuple[PipelineStatus, ...],
) -> int:
    stages = stage_states(item_state)
    if stages is None:
        return 0

    reset_count = 0
    for raw_stage_state in stages.values():
        if (
            isinstance(raw_stage_state, dict)
            and raw_stage_state.get("status") in statuses
        ):
            raw_stage_state["status"] = "pending"
            raw_stage_state["last_error"] = None
            raw_stage_state["updated_at"] = current_timestamp()
            reset_count += 1

    return reset_count


def stage_states(item_state: object) -> dict[str, object] | None:
    if not isinstance(item_state, dict):
        return None

    stages = item_state.get("stages")
    if isinstance(stages, dict):
        return stages

    return None


def remove_skipped_stages(stages: dict[str, object]) -> int:
    skipped_stages = [
        stage
        for stage, raw_stage_state in stages.items()
        if isinstance(raw_stage_state, dict)
        and raw_stage_state.get("status") == "skipped"
    ]

    for stage in skipped_stages:
        stages.pop(stage, None)

    return len(skipped_stages)


def current_timestamp() -> str:
    return datetime.now(tz=UTC).isoformat()
