from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from src.config import Config
from src.logger import log
from src.matcher import ExifDatetimeReader, LocationMatcher
from src.media_dispatcher import process_media
from src.memories import Memory, MemoriesRepository
from src.overlay import OverlayStage
from src.pipeline.stage_concurrency import StageConcurrency
from src.scanner import FolderScanner, MediaPair
from src.ui import StatsManager, UpdateUI


@dataclass
class PairResult:
    media_id: str
    overlay_applied: bool = False
    matched: bool = False
    processed: bool = False
    deleted_unmatched: bool = False
    failed: bool = False


class MemoriesPipeline:
    def run(self) -> None:
        if Config.cli_options["overlay_mode"] == "off":
            OverlayStage.purge_overlays()

        pairs = FolderScanner(Config.memories_folder).run()

        if not pairs:
            log("No media pairs found to process.", "info")
            return

        matcher = LocationMatcher(self._load_memories())
        stage_concurrency = StageConcurrency.from_options(Config.cli_options)
        StatsManager.total_files = len(pairs)

        futures = self._submit_pairs(pairs, matcher, stage_concurrency)

        try:
            self._collect_results(futures)
        except KeyboardInterrupt:
            self._handle_keyboard_interrupt(futures)

    @staticmethod
    def _load_memories() -> list[Memory]:
        raw_items = MemoriesRepository().get_raw_items()
        return [Memory.model_validate(item) for item in raw_items]

    def _submit_pairs(
        self,
        pairs: list[MediaPair],
        matcher: LocationMatcher,
        stage_concurrency: StageConcurrency,
    ) -> dict[Future, MediaPair]:
        max_workers = stage_concurrency.pair_worker_capacity(Config.cli_options)
        executor = ThreadPoolExecutor(max_workers=max_workers)

        futures = {}
        for pair in pairs:
            future = executor.submit(
                self._process_pair,
                pair,
                matcher,
                stage_concurrency,
            )
            futures[future] = pair

        return futures

    def _collect_results(self, futures: dict[Future, MediaPair]) -> None:
        for future in as_completed(futures):
            pair = futures[future]
            try:
                result = future.result()
            except Exception as error:
                result = PairResult(media_id=pair.media_id, failed=True)
                log(
                    f"Unexpected failure processing '{pair.media_id}': {error}",
                    "error",
                    "ERR",
                )

            self._update_stats(result)
            UpdateUI().run()

    def _handle_keyboard_interrupt(self, futures: dict[Future, MediaPair]) -> None:
        log("KeyboardInterrupt received. Finishing in-flight pairs...", "info")
        UpdateUI().run("interrupted")
        unfinished = {f: futures[f] for f in futures if not f.done()}
        self._collect_results(unfinished)
        log("All in-flight pairs finished. Exiting.", "info")

    def _process_pair(
        self,
        pair: MediaPair,
        matcher: LocationMatcher,
        stage_concurrency: StageConcurrency,
    ) -> PairResult:
        result = PairResult(media_id=pair.media_id)

        if pair.main_path is None or not pair.main_path.exists():
            log(f"No usable main file for '{pair.media_id}'", "error", "PAIR")
            result.failed = True
            return result

        file_path = self._run_overlay_stage(pair, result, stage_concurrency)
        if file_path is None:
            return result

        memory = None
        if Config.cli_options["write_metadata"]:
            captured_at = ExifDatetimeReader(file_path).run()
            memory = matcher.match_one(pair.media_id, captured_at)
            result.matched = memory is not None

            if memory is None and Config.cli_options["strict_location"]:
                file_path.unlink(missing_ok=True)
                result.deleted_unmatched = True
                log(f"Deleted unmatched file for '{pair.media_id}' (--strict)", "info")
                return result

        process_media(memory, file_path, stage_concurrency)
        result.processed = True
        return result

    @staticmethod
    def _run_overlay_stage(
        pair: MediaPair,
        result: PairResult,
        stage_concurrency: StageConcurrency,
    ) -> Path | None:
        try:
            overlay_stage = OverlayStage(pair)
            if pair.overlay_path:
                with stage_concurrency.overlay_applier_slot():
                    file_path = overlay_stage.run()
            else:
                file_path = overlay_stage.run()
        except Exception as error:
            log(f"Overlay stage failed for '{pair.media_id}': {error}", "error", "OVR")
            result.failed = True
            return None

        result.overlay_applied = pair.overlay_path is not None
        return file_path

    @staticmethod
    def _update_stats(result: PairResult) -> None:
        StatsManager.processed_count += 1
        if result.failed:
            StatsManager.failed_count += 1
        if result.overlay_applied:
            StatsManager.overlay_applied_count += 1
        if result.matched:
            StatsManager.matched_count += 1
        else:
            StatsManager.unmatched_count += 1
        if result.deleted_unmatched:
            StatsManager.deleted_unmatched_count += 1