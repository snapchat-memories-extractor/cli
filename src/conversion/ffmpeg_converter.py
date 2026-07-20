import subprocess
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe

from src.config import Config, FFmpegConfig
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
            raise RuntimeError("Video conversion failed") from error

        temp_path.replace(self.file_path)
        return self.file_path

    def _build_ffmpeg_command(self, temp_path: Path) -> list[str]:
        codec = FFmpegConfig.get_video_codec()
        av1_crf = Config.cli_options["av1_crf"]

        command = [
            get_ffmpeg_exe(),
            "-y", # Overwrite output files without asking
            "-i", str(self.file_path),
            "-map_metadata", "0", # Copy metadata from input to output
            "-c:a", "copy", # Copy audio streams without re-encoding
            "-c:v", codec,
            "-crf", av1_crf
        ]

        # At this point we are 100% sure that the user wants to convert to AV1, so we can add the AV1-specific parameters
        command += ["-b:v", "0"] # Set video bitrate to 0 for CRF mode (quality-based encoding)

        # Add AV1 speed parameters based on the selected encoder and user preferences
        command += FFmpegConfig.get_av1_speed_params() 
        command += FFmpegConfig.get_av1_quality_params()
        command += FFmpegConfig.get_av1_film_grain_params()

        # Add pixel format parameter based on user preference
        command += [
            "-pix_fmt",
            FFmpegConfig.get_video_pixel_format(),
            str(temp_path),
        ]

        return command
