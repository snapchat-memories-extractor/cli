from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path

from src.config import Config
from src.core.failure_store import FailureStore
from src.core.stage_concurrency import StageConcurrency
from src.helpers import is_image
from src.logger import log
from src.matcher import ExifDatetimeReader, LocationMatcher
from src.memories import MemoriesRepository, Memory
from src.metadata.image_metadata_writer import ImageMetadataWriter
from src.metadata.video_metadata_writer import VideoMetadataWriter
from src.ui import StatsManager


class MetadataPhase:
    def __init__(
        self,
        stage_concurrency: StageConcurrency,
        failure_store: FailureStore,
    ) -> None:
        self.stage_concurrency = stage_concurrency
        self.failure_store = failure_store

    def run(self, media_files: list[Path]) -> None:
        if not Config.cli_options["write_metadata"]:
            return

        matcher = LocationMatcher(self._load_memories())
        with ThreadPoolExecutor(
            max_workers=self.stage_concurrency.gps_writer.max_workers
        ) as executor:
            futures = self._submit_media(executor, media_files, matcher)

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
        executor: ThreadPoolExecutor,
        media_files: list[Path],
        matcher: LocationMatcher,
    ) -> dict[Future, Path]:
        futures = {}
        for file_path in media_files:
            future = executor.submit(self._apply_metadata, file_path, matcher)
            futures[future] = file_path

        return futures

    def _collect_results(self, futures: dict[Future, Path]) -> None:
        for future in as_completed(futures):
            file_path = futures[future]
            try:
                result = future.result()
            except Exception as error:
                StatsManager.record_failed()
                self.failure_store.move_file(file_path)
                log(
                    f"Metadata stage failed for '{file_path}': {error}",
                    "error",
                    "META",
                )
            else:
                self._update_stats(result)

    def _handle_keyboard_interrupt(self, futures: dict[Future, Path]) -> None:
        log(
            "KeyboardInterrupt received. Finishing in-flight metadata writes...",
            "info",
        )
        unfinished = {f: futures[f] for f in futures if not f.done()}
        self._collect_results(unfinished)
        log("All in-flight metadata writes finished.", "info")

    def _apply_metadata(
        self,
        file_path: Path,
        matcher: LocationMatcher,
    ) -> bool:
        captured_at = ExifDatetimeReader(file_path).run()
        memory = matcher.match_one(file_path.stem, captured_at)

        if memory is None:
            if Config.cli_options["strict_location"]:
                file_path.unlink(missing_ok=True)
                log(f"Deleted unmatched file for '{file_path.stem}' (--strict)", "info")
                return False
            return False

        with self.stage_concurrency.gps_writer_slot():
            self._write_metadata(memory, file_path)

        return True

    @staticmethod
    def _write_metadata(memory: Memory, file_path: Path) -> None:
        if is_image(file_path):
            ImageMetadataWriter(memory, file_path).write_image_metadata()
        else:
            VideoMetadataWriter(memory, file_path).write_video_metadata()

    @staticmethod
    def _update_stats(matched: bool) -> None:
        if matched:
            StatsManager.record_matched()
        else:
            StatsManager.record_unmatched()
