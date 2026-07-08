from pathlib import Path

from src.config import Config
from src.conversion import ConversionPhase
from src.logger import log
from src.metadata import MetadataPhase
from src.overlay import OverlayPhase
from src.pipeline.stage_concurrency import StageConcurrency
from src.scanner import FolderScanner
from src.ui import StatsManager


class MemoriesPipeline:
    def run(self) -> None:
        stage_concurrency = StageConcurrency.from_options(Config.cli_options)
        OverlayPhase(stage_concurrency).run()

        media_files = FolderScanner(Config.memories_folder).scan_media_files()
        StatsManager.total_files = len(media_files)

        if not media_files:
            log("No media files found to process.", "info")
            return

        metadata_failed_files = MetadataPhase(stage_concurrency).run(media_files)
        media_files = self._scan_processable_files(metadata_failed_files)
        StatsManager.total_files = len(media_files)

        if not media_files:
            log("No media files left to convert.", "info")
            return

        ConversionPhase(stage_concurrency).run(media_files)

    def _scan_processable_files(self, failed_files: set[Path]) -> list[Path]:
        media_files = FolderScanner(Config.memories_folder).scan_media_files()
        return [file_path for file_path in media_files if file_path not in failed_files]
