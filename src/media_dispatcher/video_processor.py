from pathlib import Path
from typing import TYPE_CHECKING

from src.config import Config
from src.conversion import VideoConverter

if TYPE_CHECKING:
    from src.pipeline.stage_concurrency import StageConcurrency


class ProcessVideo:
    def run(
        self,
        file_path: Path,
        stage_concurrency: "StageConcurrency | None" = None,
    ) -> Path:
        if self._should_process_video():
            file_path = self._convert_to_av1(file_path, stage_concurrency)

        return file_path

    def _should_process_video(self) -> bool:
        return Config.cli_options["video_codec"] == "av1"

    def _convert_to_av1(
        self,
        file_path: Path,
        stage_concurrency: "StageConcurrency | None",
    ) -> Path:
        if stage_concurrency is None:
            return VideoConverter(file_path).run()

        with stage_concurrency.av1_converter_slot():
            return VideoConverter(file_path).run()
