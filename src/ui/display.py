from collections.abc import Iterable
from pathlib import Path
from time import time

from src.config.defaults import DISPLAY_WIDTH, PROGRESS_BAR_WIDTH
from src.core.state_store import VALID_STAGES, PipelineStage, StateStore

# Just to make the display more readable
PHASE_LABELS: dict[PipelineStage, str] = {
    "overlay": "Overlay",
    "metadata": "Metadata",
    "conversion": "Conversion",
}


class Display:
    def __init__(
        self,
        state_store: StateStore,
        stage: PipelineStage,
        items: Iterable[Path],
        started_at: float,
    ) -> None:
        self.stage = stage
        self.progress = state_store.summarize_stage(items, stage)
        self.phase_index = VALID_STAGES.index(stage) + 1
        self.elapsed_time = max(0, int(time() - started_at))
        self.progress_bar = self._generate_progress_bar(
            self.progress.terminal,
            self.progress.total,
            bar_length=PROGRESS_BAR_WIDTH,
        )
        self.eta = self._calculate_eta(
            self.progress.terminal,
            self.elapsed_time,
            self.progress.remaining,
        )

    def print_display(self, state: str | None = None) -> None:
        line1 = self._get_first_line()
        line2 = self._get_progress_line()

        if state == "loading":
            line3, line4 = self._get_loading_display_lines()
        elif state == "interrupted":
            line3, line4 = self._get_interruption_display_lines()
        elif state == "finished":
            line3, line4 = self._get_finished_display_lines()
        else:
            line3, line4 = self._get_base_display_lines()

        print(f"+{'-' * DISPLAY_WIDTH}+")
        print(f"|{self._padding_line(line1)}|")
        print(f"+{'-' * DISPLAY_WIDTH}+")
        print(f"|{self._padding_line(line2)}|")
        print(f"+{'-' * DISPLAY_WIDTH}+")
        print(f"|{self._padding_line(line3)}|")
        print(f"|{self._padding_line(line4)}|")
        print(f"+{'-' * DISPLAY_WIDTH}+")

    def _get_first_line(self) -> str:
        left = " SNAPCHAT MEMORIES DOWNLOADER"
        right = f"PHASE {self.phase_index}/{len(VALID_STAGES)} "
        return left.ljust(DISPLAY_WIDTH - len(right)) + right

    def _get_progress_line(self) -> str:
        label = PHASE_LABELS[self.stage]
        return f"  {label:<10} [{self.progress_bar}] {self.progress.percent:5.1f}%"

    @staticmethod
    def _calculate_eta(current: int, elapsed_time: int, remaining: int) -> str:
        if remaining == 0:
            return "0s"
        if current == 0:
            return "calculating..."

        avg_time = elapsed_time / current
        eta = avg_time * remaining
        return Display._format_time(eta)

    @staticmethod
    def _get_loading_display_lines() -> tuple[str, str]:
        line3 = "  Preparing pipeline state."
        line4 = "  Scanning memories folder..."
        return line3, line4

    @staticmethod
    def _get_interruption_display_lines() -> tuple[str, str]:
        line3 = "  Processing interrupted by user."
        line4 = "  Finishing in-flight work, please wait..."
        return line3, line4

    def _get_finished_display_lines(self) -> tuple[str, str]:
        line3 = "  Processing complete."
        line4 = self._get_summary_line()
        return line3, line4

    def _get_base_display_lines(self) -> tuple[str, str]:
        line3 = (
            f"  Done {self.progress.done} | Running {self.progress.running} | "
            f"Skipped {self.progress.skipped} | Failed {self.progress.failed}"
        )
        line4 = self._get_summary_line()
        return line3, line4

    def _get_summary_line(self) -> str:
        return (
            f"  Items {self.progress.terminal}/{self.progress.total} | "
            f"Elapsed {self._format_time(self.elapsed_time):>10} | "
            f"ETA {self.eta:>10}"
        )

    @staticmethod
    def _format_time(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.0f}s"
        if seconds < 3600:
            return f"{seconds // 60:.0f}m {seconds % 60:.0f}s"
        return f"{seconds // 3600:.0f}h {(seconds % 3600) // 60:.0f}m"

    @staticmethod
    def _generate_progress_bar(
        current: int,
        total: int,
        bar_length: int = PROGRESS_BAR_WIDTH,
    ) -> str:
        filled_bar_length = Display._calculate_progress_bar_length(
            current,
            total,
            bar_length,
        )
        return "#" * filled_bar_length + "-" * (bar_length - filled_bar_length)

    @staticmethod
    def _calculate_progress_bar_length(
        current: int,
        total: int,
        bar_length: int,
    ) -> int:
        if total == 0:
            return bar_length

        progress = min(1.0, max(0.0, current / total))
        return int(bar_length * progress)

    @staticmethod
    def _padding_line(content: str, total_width: int = DISPLAY_WIDTH) -> str:
        if len(content) > total_width:
            return f"{content[: total_width - 3]}..."
        return content + (" " * (total_width - len(content)))
