from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path

from src.config import Config
from src.core.state_store import PipelineStateStore, PipelineStatus
from src.helpers import is_image, scan_memory_files
from src.logger import log
from src.metadata.image_metadata_writer import ImageMetadataWriter
from src.metadata.json_memory_loader import load_json_memories
from src.metadata.memory_model import Memory
from src.metadata.memory_path_matcher import match_memory_paths
from src.metadata.video_metadata_writer import VideoMetadataWriter
from src.ui import StatsManager


class MetadataPhase:
    def __init__(
        self,
        state_store: PipelineStateStore,
    ) -> None:
        self.state_store = state_store

    def run(self) -> None:
        media_files = scan_memory_files()

        if not Config.cli_options["write_metadata"]:
            self._mark_metadata_skipped(media_files)
            log("Skipping metadata phase (--no-metadata).", "info")
            return

        if not media_files:
            log("No media files found to process.", "info")
            return

        # Filter out media files that failed in previous stage
        media_files = self._filter_blocked_media(media_files)
        # Filter out media files that have already been processed in this stage
        media_files = self._filter_resumable_media(media_files)

        if not media_files:
            log("No media files eligible for metadata.", "info")
            return

        memories = load_json_memories()
        self._mark_metadata_running(media_files)
        memories, unmatched_files = match_memory_paths(media_files, memories)
        self._handle_unmatched_media_files(unmatched_files)

        if not memories:
            log("No media files matched metadata.", "info")
            return

        with ThreadPoolExecutor(
            max_workers=Config.cli_options["gps_writer_concurrency"]
        ) as executor:
            futures = self._submit_memories(executor, memories)

            try:
                self._collect_results(futures)
            except KeyboardInterrupt:
                self._handle_keyboard_interrupt(futures)

    def _mark_metadata_running(self, media_files: list[Path]) -> None:
        for file_path in media_files:
            self.state_store.mark_running(file_path, "metadata")

    def _handle_unmatched_media_files(self, media_files: list[Path]) -> None:
        for file_path in media_files:
            self._handle_unmatched_media(file_path)

    def _handle_unmatched_media(self, file_path: Path) -> None:
        if Config.cli_options["strict_location"]:
            file_path.unlink(missing_ok=True)
            log(f"Deleted unmatched file for '{file_path.stem}' (--strict)", "info")
        self.state_store.mark_skipped(file_path, "metadata")
        StatsManager.record_unmatched()

    def _submit_memories(
        self,
        executor: ThreadPoolExecutor,
        memories: list[Memory],
    ) -> dict[Future, Path]:
        futures = {}
        for memory in memories:
            file_path = self._memory_file_path(memory)
            future = executor.submit(self._apply_metadata, memory)
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

    def _apply_metadata(self, memory: Memory) -> bool:
        file_path = self._memory_file_path(memory)
        self._write_metadata(memory)
        self.state_store.mark_done(file_path, "metadata")
        return True

    def _filter_blocked_media(self, media_files: list[Path]) -> list[Path]:
        eligible = []
        for file_path in media_files:
            failed_stage = self.state_store.have_stage_failed(file_path, ("overlay",))
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
    def _write_metadata(memory: Memory) -> None:
        file_path = MetadataPhase._memory_file_path(memory)
        if is_image(file_path):
            ImageMetadataWriter(memory).write_image_metadata()
        else:
            VideoMetadataWriter(memory).write_video_metadata()

    @staticmethod
    def _memory_file_path(memory: Memory) -> Path:
        if memory.file_path is None:
            raise ValueError
        return memory.file_path

    @staticmethod
    def _update_stats(matched: bool) -> None:
        if matched:
            StatsManager.record_matched()
        else:
            StatsManager.record_unmatched()
