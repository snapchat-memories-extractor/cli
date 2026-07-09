from src.config import Config
from src.conversion.conversion_phase import ConversionPhase
from src.core.failure_store import FailureStore
from src.core.stage_concurrency import StageConcurrency
from src.logger import log
from src.metadata.metadata_phase import MetadataPhase
from src.overlay.overlay_phase import OverlayPhase
from src.scanner import FolderScanner
from src.ui import StatsManager


class MemoriesPipeline:
    def run(self) -> None:
        stage_concurrency = StageConcurrency.from_options(Config.cli_options)
        failure_store = FailureStore()
        failure_store.restore_all()

        try:
            OverlayPhase(stage_concurrency, failure_store).run()

            media_files = FolderScanner(Config.memories_folder).scan_media_files()
            StatsManager.set_total_files(len(media_files))

            if not media_files:
                log("No media files found to process.", "info")
                return

            MetadataPhase(
                stage_concurrency,
                failure_store,
            ).run(media_files)
            media_files = FolderScanner(Config.memories_folder).scan_media_files()
            StatsManager.set_total_files(len(media_files))

            if not media_files:
                log("No media files left to convert.", "info")
                return

            ConversionPhase(stage_concurrency, failure_store).run(media_files)
        finally:
            failure_store.restore_all()
