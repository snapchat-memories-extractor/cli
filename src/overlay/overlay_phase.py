from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from shutil import copy2

from src.config import Config
from src.core.state_store import PipelineStatus, StateStore
from src.helpers import (
    handle_phase_keyboard_interrupt,
    log_resumed_stage_skip,
    scan_memory_files,
)
from src.logger import log
from src.overlay.overlay_job import overlay_output_path, run_overlay_job
from src.overlay.scan_overlay_pairs import OverlayPair, scan_overlay_pairs


class OverlayPhase:
    def __init__(
        self,
        state_store: StateStore,
    ) -> None:
        self.state_store = state_store

    def run(self) -> None:
        if Config.cli_options["overlay_mode"] == "off":
            self._copy_all_main_files()
            log("Overlay phase skipped (--overlay-mode off).", "info")
            return

        pairs = scan_overlay_pairs()
        self._copy_existing_overlaid_files()
        if Config.cli_options["overlay_mode"] == "both":
            self._copy_all_main_files(mark_skipped=False)
        self._copy_unpaired_main_files(pairs)
        # Filter out files that have already been processed in this stage
        pairs = self._filter_resumable_pairs(pairs)

        if not pairs:
            log("No overlay pairs found to process.", "info")
            return

        with ThreadPoolExecutor(
            max_workers=Config.cli_options["overlay_applier_concurrency"]
        ) as executor:
            futures = self._submit_pairs(executor, pairs)

            try:
                self._collect_results(futures)
            except KeyboardInterrupt:
                handle_phase_keyboard_interrupt(
                    futures,
                    self._collect_results,
                    "overlays",
                )

    def _submit_pairs(
        self,
        executor: ThreadPoolExecutor,
        pairs: list[OverlayPair],
    ) -> dict[Future, OverlayPair]:
        futures = {}
        for pair in pairs:
            futures[executor.submit(self._apply_overlay, pair)] = pair
        return futures

    def _collect_results(self, futures: dict[Future, OverlayPair]) -> None:
        for future in as_completed(futures):
            pair = futures[future]
            try:
                future.result()
            except Exception as error:
                self.state_store.mark_failed(pair.main_path, "overlay", str(error))
                self.state_store.mark_failed(pair.overlay_path, "overlay", str(error))
                log(
                    f"Overlay stage failed for '{pair.media_id}': {error}",
                    "error",
                    "OVR",
                )

    def _apply_overlay(self, pair: OverlayPair) -> None:
        if not pair.main_path.exists():
            raise FileNotFoundError(pair.main_path)

        self.state_store.mark_running(pair.main_path, "overlay")
        self.state_store.mark_running(pair.overlay_path, "overlay")

        output_path = run_overlay_job(pair)
        copied_main_path = None
        if Config.cli_options["overlay_mode"] == "both":
            copied_main_path = self._copy_to_output(pair.main_path)

        self.state_store.mark_done(pair.main_path, "overlay")
        self.state_store.mark_done(pair.overlay_path, "overlay")
        self.state_store.mark_done(output_path, "overlay")
        if copied_main_path is not None:
            self.state_store.mark_done(copied_main_path, "overlay")

    def _filter_resumable_pairs(self, pairs: list[OverlayPair]) -> list[OverlayPair]:
        eligible = []
        for pair in pairs:
            status = self._terminal_overlay_status(pair)
            if status:
                log_resumed_stage_skip("overlay", pair.media_id, status)
            else:
                eligible.append(pair)
        return eligible

    def _terminal_overlay_status(self, pair: OverlayPair) -> PipelineStatus | None:
        status = (
            self.state_store.terminal_status(pair.main_path, "overlay")
            or self.state_store.terminal_status(pair.overlay_path, "overlay")
        )
        if status == "done" and not overlay_output_path(pair).exists():
            return None
        return status

    def _copy_all_main_files(self, *, mark_skipped: bool = True) -> None:
        for path in scan_memory_files():
            if path.stem.endswith("-main"):
                self._copy_to_output(path)
                if mark_skipped:
                    self.state_store.mark_skipped(path, "overlay")

    def _copy_unpaired_main_files(self, pairs: list[OverlayPair]) -> None:
        paired_mains = {pair.main_path for pair in pairs}
        for path in scan_memory_files():
            if path.stem.endswith("-main") and path not in paired_mains:
                output_path = self._copy_to_output(path)
                self.state_store.mark_skipped(path, "overlay")
                self.state_store.mark_skipped(output_path, "overlay")

    def _copy_existing_overlaid_files(self) -> None:
        for path in scan_memory_files():
            if path.stem.endswith("-overlaid"):
                output_path = self._copy_to_output(path)
                self.state_store.mark_done(output_path, "overlay")

    @staticmethod
    def _copy_to_output(path: Path) -> Path:
        Config.output_folder.mkdir(parents=True, exist_ok=True)
        output_path = Config.output_folder / path.name

        if path.resolve() != output_path.resolve():
            copy2(path, output_path)
        return output_path
