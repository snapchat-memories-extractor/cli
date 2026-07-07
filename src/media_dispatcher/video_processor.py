from pathlib import Path

from src.config import Config
from src.converters import VideoConverter
from src.memories import Memory
from src.metadata import VideoMetadataWriter


class ProcessVideo:
    def run(self, memory: Memory | None, file_path: Path) -> Path:
        if self._should_process_video():
            file_path = VideoConverter(file_path).run()

        if Config.cli_options["write_metadata"] and memory is not None:
            file_path = VideoMetadataWriter(memory, file_path).write_video_metadata()

        return file_path

    def _should_process_video(self) -> bool:
        return bool(
            Config.cli_options["video_codec"] != "h264"
            or Config.cli_options["ffmpeg_pixel_format"] != "yuv420p"
            or not Config.cli_options["write_metadata"]
            or Config.cli_options["crf"] is not None
        )