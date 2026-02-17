import subprocess
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe

from src.config import FFmpegConfig


class VideoConverter:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def run(self) -> Path:
        command = self._build_ffmpeg_command()
        subprocess.run(command, check=True)
        return self.file_path

    def _build_ffmpeg_command(self) -> list[str]:
        return [
            get_ffmpeg_exe(),
            "-y",
            "-i",
            str(self.file_path),
            "-c:a",
            "copy",
            "-c:v",
            FFmpegConfig.get_video_codec(),
            "-crf",
            FFmpegConfig.get_video_crf(),
            "-preset",
            FFmpegConfig.get_ffmpeg_preset(),
            "-pix_fmt",
            FFmpegConfig.get_video_pixel_format(),
            str(self.file_path),
        ]
