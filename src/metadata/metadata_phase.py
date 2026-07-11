from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path

from src.config import Config
from src.core.state_store import PipelineStateStore, PipelineStatus
from src.core.stage_concurrency import StageConcurrency
from src.helpers import is_image
from src.logger import log
from src.metadata.exif_datetime_reader import ExifDatetimeReader
from src.metadata.image_metadata_writer import ImageMetadataWriter
from src.metadata.location_matcher import LocationMatcher
from src.metadata.memories_repository import MemoriesRepository
from src.metadata.memory_model import Memory
from src.metadata.video_metadata_writer import VideoMetadataWriter
from src.ui import StatsManager


class MetadataPhase:
    def __init__(
        self,
        stage_concurrency: StageConcurrency,
        state_store: PipelineStateStore,
    ) -> None:
        self.stage_concurrency = stage_concurrency
        self.state_store = state_store

    def run(self, media_files: list[Path]) -> None:
        if not Config.cli_options["write_metadata"]:
            self._mark_metadata_skipped(media_files)
            return

        media_files = self._filter_blocked_media(media_files)
        media_files = self._filter_resumable_media(media_files)
        if not media_files:
            log("No media files eligible for metadata.", "info")
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
                self.state_store.mark_failed(file_path, "metadata", str(error))
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
        self.state_store.mark_running(file_path, "metadata")
        captured_at = ExifDatetimeReader(file_path).run()
        memory = matcher.match_one(file_path.stem, captured_at)

        if memory is None:
            if Config.cli_options["strict_location"]:
                file_path.unlink(missing_ok=True)
                log(f"Deleted unmatched file for '{file_path.stem}' (--strict)", "info")
            self.state_store.mark_skipped(file_path, "metadata")
            return False

        with self.stage_concurrency.gps_writer_slot():
            self._write_metadata(memory, file_path)

        self.state_store.mark_done(file_path, "metadata")
        return True

    def _filter_blocked_media(self, media_files: list[Path]) -> list[Path]:
        eligible = []
        for file_path in media_files:
            failed_stage = self.state_store.failed_stage(file_path, ("overlay",))
            if failed_stage:
                self.state_store.mark_skipped(file_path, "metadata")
                log(
                    f"Skipping metadata for '{file_path}' "
                    f"because {failed_stage} failed.",
                    "warning",
                )
            else:
                eligible.append(file_path)
        return eligible

    def _filter_resumable_media(self, media_files: list[Path]) -> list[Path]:
        eligible = []
        for file_path in media_files:
            status = self.state_store.terminal_status(file_path, "metadata")
            if status:
                self._log_resumed_metadata_skip(file_path, status)
            else:
                eligible.append(file_path)
        return eligible

    def _mark_metadata_skipped(self, media_files: list[Path]) -> None:
        for file_path in media_files:
            self.state_store.mark_skipped(file_path, "metadata")

    @staticmethod
    def _log_resumed_metadata_skip(
        file_path: Path,
        status: PipelineStatus,
    ) -> None:
        if status == "failed":
            log(
                f"Skipping metadata for '{file_path}' because it failed earlier.",
                "warning",
            )
        else:
            log(
                f"Skipping metadata for '{file_path}' "
                f"because it is already {status}.",
                "info",
            )

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
