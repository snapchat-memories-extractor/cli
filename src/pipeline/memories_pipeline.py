from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from src.config import Config
from src.logger import log
from src.matcher import ExifDatetimeReader, LocationMatcher
from src.media_dispatcher import process_media
from src.memories import MemoriesRepository, Memory
from src.overlay import OverlayPhase
from src.pipeline.stage_concurrency import StageConcurrency
from src.scanner import FolderScanner
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
        stage_concurrency = StageConcurrency.from_options(Config.cli_options)
        OverlayPhase(stage_concurrency).run()

        media_files = FolderScanner(Config.memories_folder).scan_media_files()
        StatsManager.total_files = len(media_files)

        if not media_files:
            log("No media files found to process.", "info")
            return

        matcher = None
        if Config.cli_options["write_metadata"]:
            matcher = LocationMatcher(self._load_memories())

        futures = self._submit_media(
            media_files,
            matcher,
            stage_concurrency,
        )

        try:
            self._collect_results(futures)
        except KeyboardInterrupt:
            self._handle_keyboard_interrupt(futures)

    @staticmethod
    def _load_memories() -> list[Memory]:
        raw_items = MemoriesRepository().get_raw_items()
        return [Memory.model_validate(item) for item in raw_items]

    def _submit_media(
        self,
        media_files: list[Path],
        matcher: LocationMatcher | None,
        stage_concurrency: StageConcurrency,
    ) -> dict[Future, Path]:
        max_workers = stage_concurrency.pair_worker_capacity(Config.cli_options)
        executor = ThreadPoolExecutor(max_workers=max_workers)

        futures = {}
        for file_path in media_files:
            future = executor.submit(
                self._process_media,
                file_path,
                matcher,
                stage_concurrency,
            )
            futures[future] = file_path

        return futures

    def _collect_results(self, futures: dict[Future, Path]) -> None:
        for future in as_completed(futures):
            file_path = futures[future]
            try:
                result = future.result()
            except Exception as error:
                result = PairResult(media_id=file_path.stem, failed=True)
                log(
                    f"Unexpected failure processing '{file_path}': {error}",
                    "error",
                    "ERR",
                )

            self._update_stats(result)
            UpdateUI().run()

    def _handle_keyboard_interrupt(self, futures: dict[Future, Path]) -> None:
        log("KeyboardInterrupt received. Finishing in-flight pairs...", "info")
        UpdateUI().run("interrupted")
        unfinished = {f: futures[f] for f in futures if not f.done()}
        self._collect_results(unfinished)
        log("All in-flight pairs finished. Exiting.", "info")

    def _process_media(
        self,
        file_path: Path,
        matcher: LocationMatcher | None,
        stage_concurrency: StageConcurrency,
    ) -> PairResult:
        media_id = file_path.stem
        result = PairResult(media_id=media_id)

        memory = None
        if Config.cli_options["write_metadata"]:
            assert matcher is not None
            captured_at = ExifDatetimeReader(file_path).run()
            memory = matcher.match_one(media_id, captured_at)
            result.matched = memory is not None

            if memory is None and Config.cli_options["strict_location"]:
                file_path.unlink(missing_ok=True)
                result.deleted_unmatched = True
                log(
                    f"Deleted unmatched file for '{media_id}' (--strict)",
                    "info",
                )
                return result

        process_media(memory, file_path, stage_concurrency)
        result.processed = True
        return result

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
