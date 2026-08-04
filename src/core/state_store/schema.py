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
RETRYABLE_STATUSES: tuple[PipelineStatus, ...] = ("failed",)


@dataclass(frozen=True)
class StageState:
    status: PipelineStatus = "pending"
    attempts: int = 0
    last_error: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class StageProgress:
    stage: PipelineStage
    total: int
    pending: int = 0
    running: int = 0
    done: int = 0
    failed: int = 0
    skipped: int = 0

    @property
    def terminal(self) -> int:
        return self.done + self.failed + self.skipped

    @property
    def remaining(self) -> int:
        return max(0, self.total - self.terminal)

    @property
    def percent(self) -> float:
        if self.total == 0:
            return 100.0
        return min(100.0, max(0.0, self.terminal / self.total * 100))
