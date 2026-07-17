from collections.abc import Callable
from concurrent.futures import Future
from typing import TypeVar

from src.core.state_store import PipelineStatus
from src.logger import log

FutureValue = TypeVar("FutureValue")


def log_resumed_stage_skip(
    stage: str,
    item_name: str,
    status: PipelineStatus,
) -> None:
    if status == "failed":
        log(
            f"Skipping {stage} for '{item_name}' because it failed earlier.",
            "warning",
        )
    else:
        log(
            f"Skipping {stage} for '{item_name}' because it is already {status}.",
            "info",
        )


def handle_phase_keyboard_interrupt(
    futures: dict[Future, FutureValue],
    collect_results: Callable[[dict[Future, FutureValue]], None],
    work_name: str,
) -> None:
    log(f"KeyboardInterrupt received. Finishing in-flight {work_name}...", "info")
    unfinished = {
        future: value for future, value in futures.items() if not future.done()
    }
    collect_results(unfinished)
    log(f"All in-flight {work_name} finished.", "info")
