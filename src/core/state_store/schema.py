from dataclasses import dataclass
from typing import Literal, TypeAlias

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
TERMINAL_STATUSES: tuple[PipelineStatus, ...] = ("done", "failed", "skipped")
RETRYABLE_STATUSES: tuple[PipelineStatus, ...] = ("failed", "skipped")


@dataclass(frozen=True)
class StageState:
    status: PipelineStatus = "pending"
    attempts: int = 0
    last_error: str | None = None
    updated_at: str | None = None
