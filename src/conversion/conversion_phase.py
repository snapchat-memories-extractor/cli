from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path

from src.config import Config
from src.conversion.ffmpeg_converter import VideoConverter
from src.conversion.jxl_converter import JXLConverter
from src.core.pipeline_state_store import PipelineStateStore
from src.core.stage_concurrency import StageConcurrency
from src.helpers import is_image
from src.logger import log
from src.ui import StatsManager, UpdateUI


class ConversionPhase:
    def __init__(
        self,
        stage_concurrency: StageConcurrency,
        state_store: PipelineStateStore,
    ) -> None:
        self.stage_concurrency = stage_concurrency
        self.state_store = state_store

    def run(self, media_files: list[Path]) -> None:
        media_files = self._filter_blocked_media(media_files)
        media_files = self._filter_resumable_media(media_files)
        StatsManager.set_total_files(len(media_files))
        if not media_files:
            log("No media files eligible for conversion.", "info")
            return

        max_workers = self.stage_concurrency.conversion_worker_capacity(
            Config.cli_options
        )
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = self._submit_media(executor, media_files)

            try:
                self._collect_results(futures)
            except KeyboardInterrupt:
                self._handle_keyboard_interrupt(futures)

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
                StatsManager.record_failed()
                self.state_store.mark_failed(file_path, "conversion", str(error))
                log(
                    f"Unexpected failure processing '{file_path}': {error}",
                    "error",
                    "ERR",
                )

            StatsManager.record_processed()
            UpdateUI().run()

    def _handle_keyboard_interrupt(self, futures: dict[Future, Path]) -> None:
        log("KeyboardInterrupt received. Finishing in-flight conversions...", "info")
        UpdateUI().run("interrupted")
        unfinished = {f: futures[f] for f in futures if not f.done()}
        self._collect_results(unfinished)
        log("All in-flight conversions finished. Exiting.", "info")

    def _process_media(self, file_path: Path) -> None:
        if is_image(file_path):
            self._process_image(file_path)
            return

        self._process_video(file_path)

    def _process_image(self, file_path: Path) -> None:
        self.state_store.mark_running(file_path, "conversion")
        if Config.cli_options["convert_to_jxl"]:
            with self.stage_concurrency.jxl_converter_slot():
                output_path = JXLConverter(file_path).run()
            self.state_store.mark_done(
                file_path,
                "conversion",
                output_path=output_path,
            )
            self._mark_converted_output(file_path, output_path)
        else:
            self.state_store.mark_skipped(file_path, "conversion")

    def _process_video(self, file_path: Path) -> None:
        self.state_store.mark_running(file_path, "conversion")
        if Config.cli_options["video_codec"] == "av1":
            with self.stage_concurrency.av1_converter_slot():
                output_path = VideoConverter(file_path).run()
            self.state_store.mark_done(
                file_path,
                "conversion",
                output_path=output_path,
            )
        else:
            self.state_store.mark_skipped(file_path, "conversion")

    def _filter_blocked_media(self, media_files: list[Path]) -> list[Path]:
        eligible = []
        for file_path in media_files:
            failed_stage = self.state_store.failed_stage(
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
            if self._should_skip_resumed_conversion(file_path, status):
                self._log_resumed_conversion_skip(file_path, status)
            else:
                eligible.append(file_path)
        return eligible

    def _mark_converted_output(self, input_path: Path, output_path: Path) -> None:
        self.state_store.mark_done(
            output_path,
            "conversion",
            output_path=output_path,
        )
        self._copy_terminal_state(input_path, output_path, "overlay")
        self._copy_terminal_state(input_path, output_path, "metadata")

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

    def _should_skip_resumed_conversion(
        self,
        file_path: Path,
        status: str,
    ) -> bool:
        if status in ("done", "failed"):
            return True
        return status == "skipped" and not self._conversion_enabled(file_path)

    @staticmethod
    def _log_resumed_conversion_skip(file_path: Path, status: str) -> None:
        if status == "failed":
            log(
                f"Skipping conversion for '{file_path}' because it failed earlier.",
                "warning",
            )
        else:
            log(
                f"Skipping conversion for '{file_path}' "
                f"because it is already {status}.",
                "info",
            )

    @staticmethod
    def _conversion_enabled(file_path: Path) -> bool:
        if is_image(file_path):
            return Config.cli_options["convert_to_jxl"]
        return Config.cli_options["video_codec"] == "av1"
