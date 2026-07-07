from pathlib import Path
from typing import TYPE_CHECKING

from src.config import Config
from src.converters import VideoConverter
from src.memories import Memory
from src.metadata import VideoMetadataWriter

if TYPE_CHECKING:
    from src.pipeline.stage_concurrency import StageConcurrency


class ProcessVideo:
    def run(
        self,
        memory: Memory | None,
        file_path: Path,
        stage_concurrency: "StageConcurrency | None" = None,
    ) -> Path:
        if self._should_process_video():
            file_path = VideoConverter(file_path).run()

        if Config.cli_options["write_metadata"] and memory is not None:
            file_path = self._write_video_metadata(
                memory,
                file_path,
                stage_concurrency,
            )

        return file_path

    def _should_process_video(self) -> bool:
        return Config.cli_options["video_codec"] == "av1"

    def _write_video_metadata(
        self,
        memory: Memory,
        file_path: Path,
        stage_concurrency: "StageConcurrency | None",
    ) -> Path:
        if stage_concurrency is None:
            return VideoMetadataWriter(memory, file_path).write_video_metadata()

        with stage_concurrency.gps_writer_slot():
            return VideoMetadataWriter(memory, file_path).write_video_metadata()
