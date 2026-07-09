from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from src.config import Config
from src.logger import log
from src.matcher import ExifDatetimeReader, LocationMatcher
from src.memories import MemoriesRepository, Memory
from src.metadata.image_metadata_writer import ImageMetadataWriter
from src.metadata.video_metadata_writer import VideoMetadataWriter
from src.pipeline.failure_store import FailureStore
from src.pipeline.stage_concurrency import StageConcurrency
from src.ui import StatsManager

IMAGE_SUFFIXES = {".jpg", ".jpeg"}


@dataclass(frozen=True)
class MetadataResult:
    matched: bool = False


class MetadataPhase:
    def __init__(
        self,
        stage_concurrency: StageConcurrency,
        failure_store: FailureStore,
    ) -> None:
        self.stage_concurrency = stage_concurrency
        self.failure_store = failure_store

    def run(self, media_files: list[Path]) -> set[Path]:
        if not Config.cli_options["write_metadata"]:
            return set()

        matcher = LocationMatcher(self._load_memories())
        futures = self._submit_media(media_files, matcher)

        try:
            return self._collect_results(futures)
        except KeyboardInterrupt:
            return self._handle_keyboard_interrupt(futures)

    @staticmethod
    def _load_memories() -> list[Memory]:
        raw_items = MemoriesRepository().get_raw_items()
        return [Memory.model_validate(item) for item in raw_items]

    def _submit_media(
        self,
        media_files: list[Path],
        matcher: LocationMatcher,
    ) -> dict[Future, Path]:
        executor = ThreadPoolExecutor(
            max_workers=self.stage_concurrency.gps_writer.max_workers
        )

        futures = {}
        for file_path in media_files:
            future = executor.submit(self._apply_metadata, file_path, matcher)
            futures[future] = file_path

        return futures

    def _collect_results(self, futures: dict[Future, Path]) -> set[Path]:
        failed_files = set()
        for future in as_completed(futures):
            file_path = futures[future]
            try:
                result = future.result()
            except Exception as error:
                failed_files.add(file_path)
                StatsManager.record_failed()
                self.failure_store.move_file(file_path)
                log(
                    f"Metadata stage failed for '{file_path}': {error}",
                    "error",
                    "META",
                )
            else:
                self._update_stats(result)

        return failed_files

    def _handle_keyboard_interrupt(self, futures: dict[Future, Path]) -> set[Path]:
        log(
            "KeyboardInterrupt received. Finishing in-flight metadata writes...",
            "info",
        )
        unfinished = {f: futures[f] for f in futures if not f.done()}
        failed_files = self._collect_results(unfinished)
        log("All in-flight metadata writes finished.", "info")
        return failed_files

    def _apply_metadata(
        self,
        file_path: Path,
        matcher: LocationMatcher,
    ) -> MetadataResult:
        captured_at = ExifDatetimeReader(file_path).run()
        memory = matcher.match_one(file_path.stem, captured_at)

        if memory is None:
            if Config.cli_options["strict_location"]:
                file_path.unlink(missing_ok=True)
                log(f"Deleted unmatched file for '{file_path.stem}' (--strict)", "info")
                return MetadataResult()
            return MetadataResult()

        with self.stage_concurrency.gps_writer_slot():
            self._write_metadata(memory, file_path)

        return MetadataResult(matched=True)

    @staticmethod
    def _write_metadata(memory: Memory, file_path: Path) -> None:
        if file_path.suffix.lower() in IMAGE_SUFFIXES:
            ImageMetadataWriter(memory, file_path).write_image_metadata()
        else:
            VideoMetadataWriter(memory, file_path).write_video_metadata()

    @staticmethod
    def _update_stats(result: MetadataResult) -> None:
        if result.matched:
            StatsManager.record_matched()
        else:
            StatsManager.record_unmatched()
