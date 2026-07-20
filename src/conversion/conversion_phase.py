from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path

from src.config import Config
from src.conversion.conversion_concurrency import (
    ConversionSlots,
    conversion_worker_capacity,
)
from src.conversion.ffmpeg_converter import VideoConverter
from src.conversion.jxl_converter import JXLConverter
from src.core.state_store import PipelineStateStore
from src.helpers import handle_phase_keyboard_interrupt, is_image, scan_memory_files
from src.logger import log


class ConversionPhase:
    def __init__(
        self,
        state_store: PipelineStateStore,
    ) -> None:
        self.conversion_slots = ConversionSlots.from_options()
        self.state_store = state_store

    def run(self) -> None:
        media_files = scan_memory_files()

        if (
            not Config.cli_options["convert_to_jxl"]
            and Config.cli_options["video_codec"] != "av1"
        ):
            self._mark_conversion_skipped(media_files)
            log("Conversion is disabled. Skipping.", "info")
            return

        media_files = self._filter_blocked_media(media_files)
        media_files = self._filter_resumable_media(media_files)

        if not media_files:
            log("No media files eligible for conversion.", "info")
            return

        max_workers = conversion_worker_capacity()
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = self._submit_media(executor, media_files)

            try:
                self._collect_results(futures)
            except KeyboardInterrupt:
                handle_phase_keyboard_interrupt(
                    futures,
                    self._collect_results,
                    "conversion",
                )

    def _submit_media(
        self,
        executor: ThreadPoolExecutor,
        media_files: list[Path],
    ) -> dict[Future, Path]:
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
                self.state_store.mark_failed(file_path, "conversion", str(error))
                log(
                    f"Unexpected failure processing '{file_path}': {error}",
                    "error",
                    "ERR",
                )

    def _process_media(self, file_path: Path) -> None:
        if is_image(file_path):
            self._process_image(file_path)
            return

        self._process_video(file_path)

    def _process_image(self, file_path: Path) -> None:
        self.state_store.mark_running(file_path, "conversion")

        if not Config.cli_options["convert_to_jxl"]:
            self.state_store.mark_skipped(file_path, "conversion")
            return

        with self.conversion_slots.jxl:
            output_path = JXLConverter(file_path).run()

        if output_path is None:
            self.state_store.mark_failed(
                file_path,
                "conversion",
                "JXL conversion failed",
            )
            return

        self.state_store.mark_done(file_path, "conversion")
        self.state_store.mark_done(output_path, "conversion")
        self._copy_terminal_state(file_path, output_path, "overlay")
        self._copy_terminal_state(file_path, output_path, "metadata")

    def _process_video(self, file_path: Path) -> None:
        self.state_store.mark_running(file_path, "conversion")
        if Config.cli_options["video_codec"] == "av1":
            with self.conversion_slots.av1:
                VideoConverter(file_path).run()
            self.state_store.mark_done(
                file_path,
                "conversion",
            )
        else:
            self.state_store.mark_skipped(file_path, "conversion")

    def _filter_blocked_media(self, media_files: list[Path]) -> list[Path]:
        eligible = []
        for file_path in media_files:
            failed_stage = self.state_store.have_stage_failed(
                file_path,
                ("overlay", "metadata"),
            )
            if failed_stage:
                self.state_store.mark_skipped(file_path, "conversion")
                log(
                    f"Skipping conversion for '{file_path}' "
                    f"because {failed_stage} failed.",
                    "warning",
                )
            else:
                eligible.append(file_path)
        return eligible

    def _filter_resumable_media(self, media_files: list[Path]) -> list[Path]:
        eligible = []
        for file_path in media_files:
            status = self.state_store.get_status(file_path, "conversion")
            if status:
                log(
                    f"Skipping conversion for '{file_path}' "
                    f"because it is already {status}.",
                    "info",
                )
            else:
                eligible.append(file_path)
        return eligible

    def _copy_terminal_state(
        self,
        input_path: Path,
        output_path: Path,
        stage: str,
    ) -> None:
        status = self.state_store.terminal_status(input_path, stage)
        if status == "done":
            self.state_store.mark_done(output_path, stage)
        elif status == "skipped":
            self.state_store.mark_skipped(output_path, stage)

    def _mark_conversion_skipped(self, media_files: list[Path]) -> None:
        for file_path in media_files:
            self.state_store.mark_skipped(file_path, "conversion")
