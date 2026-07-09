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
                JXLConverter(file_path).run()
            self.state_store.mark_done(file_path, "conversion")
        else:
            self.state_store.mark_skipped(file_path, "conversion")

    def _process_video(self, file_path: Path) -> None:
        self.state_store.mark_running(file_path, "conversion")
        if Config.cli_options["video_codec"] == "av1":
            with self.stage_concurrency.av1_converter_slot():
                VideoConverter(file_path).run()
            self.state_store.mark_done(file_path, "conversion")
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
