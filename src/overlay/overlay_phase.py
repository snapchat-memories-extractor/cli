from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path

from src.config import Config
from src.core.pipeline_state_store import PipelineStateStore
from src.core.stage_concurrency import StageConcurrency
from src.helpers import FolderScanner, MediaPair
from src.logger import log
from src.overlay.overlay_stage import OverlayStage
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
            pairs = FolderScanner(Config.memories_folder).scan_overlay_pairs()
            self._mark_pairs_skipped(pairs)
            self._mark_overlay_skipped_for_media()
            self._purge_non_failed_overlays()
            return

        pairs = FolderScanner(Config.memories_folder).scan_overlay_pairs()
        self._mark_unpaired_media_skipped(pairs)

        if not pairs:
            log("No overlay pairs found to process.", "info")
            self._purge_non_failed_overlays()
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
                self._purge_non_failed_overlays()

    def _submit_pairs(
        self,
        executor: ThreadPoolExecutor,
        pairs: list[MediaPair],
    ) -> dict[Future, MediaPair]:
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

    def _handle_keyboard_interrupt(self, futures: dict[Future, MediaPair]) -> None:
        log("KeyboardInterrupt received. Finishing in-flight overlays...", "info")
        unfinished = {f: futures[f] for f in futures if not f.done()}
        self._collect_results(unfinished)
        log("All in-flight overlays finished.", "info")

    def _apply_overlay(self, pair: MediaPair) -> None:
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

    def _mark_pairs_skipped(self, pairs: list[MediaPair]) -> None:
        for pair in pairs:
            self.state_store.mark_skipped(self._pair_state_key(pair), "overlay")

    def _mark_overlay_skipped_for_media(self) -> None:
        media_files = FolderScanner(Config.memories_folder).scan_media_files()
        for file_path in media_files:
            self.state_store.mark_skipped(file_path, "overlay")

    def _mark_unpaired_media_skipped(self, pairs: list[MediaPair]) -> None:
        paired_paths = self._paired_paths(pairs)
        media_files = FolderScanner(Config.memories_folder).scan_media_files()

        for file_path in media_files:
            if file_path not in paired_paths:
                self.state_store.mark_skipped(file_path, "overlay")

    @staticmethod
    def _paired_paths(pairs: list[MediaPair]) -> set[Path]:
        paired_paths = set()
        for pair in pairs:
            paired_paths.add(pair.main_path)
            paired_paths.add(pair.overlay_path)
        return paired_paths

    def _purge_non_failed_overlays(self) -> None:
        deleted = 0
        for overlay_path in Config.memories_folder.iterdir():
            if self._should_purge_overlay(overlay_path):
                overlay_path.unlink()
                deleted += 1

        if deleted:
            log(f"Deleted {deleted} overlay file(s).", "info")

    def _should_purge_overlay(self, overlay_path: Path) -> bool:
        is_overlay = overlay_path.is_file() and overlay_path.stem.endswith("-overlay")
        failed = self.state_store.get_status(overlay_path, "overlay") == "failed"
        return is_overlay and not failed

    @staticmethod
    def _pair_state_key(pair: MediaPair) -> str:
        return f"overlay-pair:{pair.media_id}"
