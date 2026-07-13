from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path

from src.config import Config
from src.core.stage_concurrency import StageConcurrency
from src.core.state_store import PipelineStateStore, PipelineStatus
from src.helpers import scan_memory_files
from src.logger import log
from src.overlay.overlay_stage import OverlayStage
from src.overlay.scan_overlay_pairs import OverlayPair, scan_overlay_pairs
from src.ui import StatsManager


class OverlayPhase:
    def __init__(
        self,
        stage_concurrency: StageConcurrency,
        state_store: PipelineStateStore,
    ) -> None:
        self.stage_concurrency = stage_concurrency
        self.state_store = state_store

    def run(self) -> None:
        if Config.cli_options["overlay_mode"] == "off":
            self._purge_overlays()
            return

        pairs = scan_overlay_pairs()
        self._purge_unpaired_overlays(pairs)

        if not pairs:
            log("No overlay pairs found to process.", "info")
            return

        with ThreadPoolExecutor(
            max_workers=self.stage_concurrency.overlay_applier.max_workers
        ) as executor:
            futures = self._submit_pairs(executor, pairs)

            try:
                self._collect_results(futures)
            except KeyboardInterrupt:
                self._handle_keyboard_interrupt(futures)
            finally:
                self._purge_overlays(required_status="done")

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
                StatsManager.record_failed()
                self.state_store.mark_failed(
                    self._pair_state_key(pair),
                    "overlay",
                    str(error),
                )
                self.state_store.mark_failed(pair.main_path, "overlay", str(error))
                self.state_store.mark_failed(pair.overlay_path, "overlay", str(error))
                log(
                    f"Overlay stage failed for '{pair.media_id}': {error}",
                    "error",
                    "OVR",
                )

    def _handle_keyboard_interrupt(self, futures: dict[Future, OverlayPair]) -> None:
        log("KeyboardInterrupt received. Finishing in-flight overlays...", "info")
        unfinished = {f: futures[f] for f in futures if not f.done()}
        self._collect_results(unfinished)
        log("All in-flight overlays finished.", "info")

    def _apply_overlay(self, pair: OverlayPair) -> None:
        if not pair.main_path.exists():
            raise FileNotFoundError(pair.main_path)

        self.state_store.mark_running(self._pair_state_key(pair), "overlay")
        self.state_store.mark_running(pair.main_path, "overlay")
        self.state_store.mark_running(pair.overlay_path, "overlay")

        with self.stage_concurrency.overlay_applier_slot():
            output_path = OverlayStage(pair).run()

        self.state_store.mark_done(self._pair_state_key(pair), "overlay")
        self.state_store.mark_done(pair.main_path, "overlay")
        self.state_store.mark_done(pair.overlay_path, "overlay")
        self.state_store.mark_done(output_path, "overlay")
        self._purge_overlay(pair.overlay_path, required_status="done")

    def _purge_unpaired_overlays(self, pairs: list[OverlayPair]) -> None:
        paired_overlays = {pair.overlay_path for pair in pairs}
        deleted = 0

        for path in scan_memory_files():
            if (
                path.stem.endswith("-overlay")
                and path not in paired_overlays
            ):
                path.unlink()
                deleted += 1

        if deleted:
            log(f"Deleted {deleted} unpaired overlay file(s).", "info")

    def _purge_overlays(self, required_status: PipelineStatus | None = None) -> None:
        deleted = 0
        for path in scan_memory_files():
            if self._purge_overlay(path, required_status):
                deleted += 1

        if deleted:
            log(f"Deleted {deleted} overlay file(s).", "info")

    def _purge_overlay(
        self,
        overlay_path: Path,
        required_status: PipelineStatus | None = None,
    ) -> bool:
        if not overlay_path.is_file() or not overlay_path.stem.endswith("-overlay"):
            return False
        if (
            required_status is not None
            and self.state_store.get_status(overlay_path, "overlay") != required_status
        ):
            return False

        overlay_path.unlink()
        return True

    @staticmethod
    def _pair_state_key(pair: OverlayPair) -> str:
        return f"overlay-pair:{pair.media_id}"
