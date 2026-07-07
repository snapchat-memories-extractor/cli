import subprocess
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe

from src.config import FFmpegConfig, Config
from src.logger import log


class VideoConverter:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def run(self) -> Path:
        temp_path = self.file_path.with_suffix(".tmp" + self.file_path.suffix)
        command = self._build_ffmpeg_command(temp_path)

        try:
            subprocess.run(command, check=True)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            temp_path.unlink(missing_ok=True)
            log(
                f"ffmpeg conversion failed for {self.file_path}: {error}",
                "warning",
            )
            return self.file_path

        temp_path.replace(self.file_path)
        return self.file_path

    def _build_ffmpeg_command(self, temp_path: Path) -> list[str]:
        codec = FFmpegConfig.get_video_codec()
        is_av1 = Config.cli_options["video_codec"] == "av1"

        command = [
            get_ffmpeg_exe(),
            "-y",
            "-i",
            str(self.file_path),
            "-c:a",
            "copy",
            "-c:v",
            codec,
            "-crf",
            FFmpegConfig.get_video_crf(),
        ]

        if is_av1:
            command += ["-b:v", "0"]
            command += FFmpegConfig.get_av1_speed_params()
            command += FFmpegConfig.get_av1_quality_params()
            command += FFmpegConfig.get_av1_film_grain_params()
        else:
            command += ["-preset", FFmpegConfig.get_ffmpeg_preset()]

        command += [
            "-pix_fmt",
            FFmpegConfig.get_video_pixel_format(),
            str(temp_path),
        ]

        return command