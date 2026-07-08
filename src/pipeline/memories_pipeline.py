from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from src.config import Config
from src.logger import log
from src.media_dispatcher import process_media
from src.metadata import MetadataPhase
from src.overlay import OverlayPhase
from src.pipeline.stage_concurrency import StageConcurrency
from src.scanner import FolderScanner
from src.ui import StatsManager, UpdateUI


@dataclass
class PairResult:
    media_id: str
    processed: bool = False
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

        metadata_failed_files = MetadataPhase(stage_concurrency).run(media_files)
        media_files = self._scan_processable_files(metadata_failed_files)
        StatsManager.total_files = len(media_files)

        if not media_files:
            log("No media files left to convert.", "info")
            return

        futures = self._submit_media(
            media_files,
            stage_concurrency,
        )

        try:
            self._collect_results(futures)
        except KeyboardInterrupt:
            self._handle_keyboard_interrupt(futures)

    def _scan_processable_files(self, failed_files: set[Path]) -> list[Path]:
        media_files = FolderScanner(Config.memories_folder).scan_media_files()
        return [file_path for file_path in media_files if file_path not in failed_files]

    def _submit_media(
        self,
        media_files: list[Path],
        stage_concurrency: StageConcurrency,
    ) -> dict[Future, Path]:
        max_workers = stage_concurrency.pair_worker_capacity(Config.cli_options)
        executor = ThreadPoolExecutor(max_workers=max_workers)

        futures = {}
        for file_path in media_files:
            future = executor.submit(
                self._process_media,
                file_path,
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
        stage_concurrency: StageConcurrency,
    ) -> PairResult:
        media_id = file_path.stem
        result = PairResult(media_id=media_id)

        process_media(file_path, stage_concurrency)
        result.processed = True
        return result

    @staticmethod
    def _update_stats(result: PairResult) -> None:
        StatsManager.processed_count += 1
        if result.failed:
            StatsManager.failed_count += 1
