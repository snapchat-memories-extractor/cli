from concurrent.futures import Future, ThreadPoolExecutor, as_completed

from src.config import Config
from src.logger import log
from src.overlay.overlay_stage import OverlayStage
from src.pipeline.stage_concurrency import StageConcurrency
from src.scanner import FolderScanner, MediaPair


class OverlayPhase:
    def __init__(self, stage_concurrency: StageConcurrency) -> None:
        self.stage_concurrency = stage_concurrency

    def run(self) -> None:
        if Config.cli_options["overlay_mode"] == "off":
            OverlayStage.purge_overlays()
            return

        pairs = FolderScanner(Config.memories_folder).scan_overlay_pairs()

        if not pairs:
            log("No overlay pairs found to process.", "info")
            OverlayStage.purge_overlays()
            return

        futures = self._submit_pairs(pairs)

        try:
            self._collect_results(futures)
        except KeyboardInterrupt:
            self._handle_keyboard_interrupt(futures)
        finally:
            OverlayStage.purge_overlays()

    def _submit_pairs(self, pairs: list[MediaPair]) -> dict[Future, MediaPair]:
        executor = ThreadPoolExecutor(
            max_workers=self.stage_concurrency.overlay_applier.max_workers
        )

        futures = {}
        for pair in pairs:
            futures[executor.submit(self._apply_overlay, pair)] = pair
        return futures

    def _collect_results(self, futures: dict[Future, MediaPair]) -> None:
        for future in as_completed(futures):
            pair = futures[future]
            try:
                future.result()
            except Exception as error:
                log(
                    f"Overlay stage failed for '{pair.media_id}': {error}",
                    "error",
                    "OVR",
                )

    def _handle_keyboard_interrupt(self, futures: dict[Future, MediaPair]) -> None:
        log("KeyboardInterrupt received. Finishing in-flight overlays...", "info")
        unfinished = {f: futures[f] for f in futures if not f.done()}
        self._collect_results(unfinished)
        log("All in-flight overlays finished.", "info")

    def _apply_overlay(self, pair: MediaPair) -> None:
        if not pair.main_path.exists():
            log(f"No usable main file for '{pair.media_id}'", "error", "PAIR")
            return

        with self.stage_concurrency.overlay_applier_slot():
            OverlayStage(pair).run()
