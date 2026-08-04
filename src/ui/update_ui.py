import sys
from collections.abc import Iterable
from pathlib import Path
from threading import RLock
from time import time

from src.config.defaults import DISPLAY_LINES
from src.core.state_store import PipelineStage, PipelineStateStore
from src.ui.display import Display


class UpdateUI:
    def __init__(
        self,
        state_store: PipelineStateStore,
        started_at: float | None = None,
    ) -> None:
        self.state_store = state_store
        self.started_at = time() if started_at is None else started_at
        self._lock = RLock()
        self._has_display = False
        self._stage: PipelineStage | None = None
        self._items: list[Path] = []
        self._state: str | None = None

    def run(
        self,
        state: str | None = None,
        stage: PipelineStage = "overlay",
        items: Iterable[Path] = (),
    ) -> None:
        self.set_phase(stage, items, state)

    def set_phase(
        self,
        stage: PipelineStage,
        items: Iterable[Path],
        state: str | None = None,
    ) -> None:
        with self._lock:
            self._stage = stage
            self._items = list(items)
            self._state = state
            self._render_locked()

    def refresh(self) -> None:
        with self._lock:
            if self._stage is None:
                return

            self._render_locked()

    def _render_locked(self) -> None:
        if self._stage is None:
            return

        if self._has_display:
            self.clear_display()

        Display(
            self.state_store,
            self._stage,
            self._items,
            self.started_at,
        ).print_display(self._state)
        self._has_display = True

    @staticmethod
    def clear_display(lines: int = DISPLAY_LINES) -> None:
        for _ in range(lines):
            sys.stdout.write("\033[F\033[K")
