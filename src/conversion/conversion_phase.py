from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path

from src.config import Config
from src.logger import log
from src.media_dispatcher import process_media
from src.pipeline.failure_store import FailureStore
from src.pipeline.stage_concurrency import StageConcurrency
from src.ui import StatsManager, UpdateUI


class ConversionPhase:
    def __init__(
        self,
        stage_concurrency: StageConcurrency,
        failure_store: FailureStore,
    ) -> None:
        self.stage_concurrency = stage_concurrency
        self.failure_store = failure_store

    def run(self, media_files: list[Path]) -> None:
        futures = self._submit_media(media_files)

        try:
            self._collect_results(futures)
        except KeyboardInterrupt:
            self._handle_keyboard_interrupt(futures)

    def _submit_media(self, media_files: list[Path]) -> dict[Future, Path]:
        max_workers = self.stage_concurrency.conversion_worker_capacity(
            Config.cli_options
        )
        executor = ThreadPoolExecutor(max_workers=max_workers)

        futures = {}
        for file_path in media_files:
            future = executor.submit(self._process_media, file_path)
            futures[future] = file_path

        return futures

    def _collect_results(self, futures: dict[Future, Path]) -> None:
        for future in as_completed(futures):
            file_path = futures[future]
            try:
                future.result()
            except Exception as error:
                StatsManager.failed_count += 1
                self.failure_store.move_file(file_path)
                log(
                    f"Unexpected failure processing '{file_path}': {error}",
                    "error",
                    "ERR",
                )

            StatsManager.processed_count += 1
            UpdateUI().run()

    def _handle_keyboard_interrupt(self, futures: dict[Future, Path]) -> None:
        log("KeyboardInterrupt received. Finishing in-flight conversions...", "info")
        UpdateUI().run("interrupted")
        unfinished = {f: futures[f] for f in futures if not f.done()}
        self._collect_results(unfinished)
        log("All in-flight conversions finished. Exiting.", "info")

    def _process_media(self, file_path: Path) -> None:
        process_media(file_path, self.stage_concurrency)
