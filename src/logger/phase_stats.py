from collections import Counter
from threading import Lock

from src.logger.log import log


class PhaseStats:
    def __init__(self, stage: str) -> None:
        self.stage = stage
        self.counts: Counter[str] = Counter()
        self.lock = Lock()

    def mark(
        self,
        status: str,
        item_name: object,
        reason: str | None = None,
        *,
        log_item: bool = True,
    ) -> None:
        with self.lock:
            self.counts[status] += 1
        if not log_item:
            return

        reason_text = f" because {reason}" if reason else ""
        log(
            f"{self.stage.capitalize()} {status} for "
            f"'{item_name}'{reason_text}.",
            "debug",
        )

    def log_summary(self) -> None:
        with self.lock:
            done = self.counts["done"]
            skipped = self.counts["skipped"]
            failed = self.counts["failed"]
        log(
            f"{self.stage.capitalize()} phase summary: "
            f"succeeded={done}, skipped={skipped}, failed={failed}.",
            "info",
        )
