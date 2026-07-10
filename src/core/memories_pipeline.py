from src.config import Config
from src.conversion.conversion_phase import ConversionPhase
from src.core.pipeline_state_store import PipelineStateStore
from src.core.stage_concurrency import StageConcurrency
from src.helpers import FolderScanner
from src.logger import log
from src.metadata.metadata_phase import MetadataPhase
from src.overlay.overlay_phase import OverlayPhase
from src.ui import StatsManager


class MemoriesPipeline:
    def run(self) -> None:
        stage_concurrency = StageConcurrency.from_options(Config.cli_options)
        state_store = PipelineStateStore()
        self._prepare_state(state_store)

        OverlayPhase(stage_concurrency, state_store).run()

        media_files = FolderScanner(Config.memories_folder).scan_media_files()
        StatsManager.set_total_files(len(media_files))

        if not media_files:
            log("No media files found to process.", "info")
            self._delete_state_if_successful(state_store)
            return

        MetadataPhase(
            stage_concurrency,
            state_store,
        ).run(media_files)
        media_files = FolderScanner(Config.memories_folder).scan_media_files()
        StatsManager.set_total_files(len(media_files))

        if not media_files:
            log("No media files left to convert.", "info")
            self._delete_state_if_successful(state_store)
            return

        ConversionPhase(stage_concurrency, state_store).run(media_files)
        self._delete_state_if_successful(state_store)

    @staticmethod
    def _delete_state_if_successful(state_store: PipelineStateStore) -> None:
        if not state_store.has_failures():
            state_store.delete()

    @staticmethod
    def _prepare_state(state_store: PipelineStateStore) -> None:
        if Config.cli_options["reset_state"]:
            log("Resetting pipeline state before run.", "info")
            state_store.delete()
        elif Config.cli_options["retry_failed"]:
            state_store.reset_retryable()

        state_store.reset_running()
