import subprocess
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe

from src.config import Config, FFmpegConfig


class VideoConverter:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def run(self) -> Path:
        temp_path = self.file_path.with_suffix(".tmp" + self.file_path.suffix)
        command = self._build_ffmpeg_command(temp_path)
        timeout = Config.cli_options["ffmpeg_timeout"]

        try:
            subprocess.run(
                command,
                check=True,
                timeout=timeout,
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            temp_path.unlink(missing_ok=True)
            message = f"Video conversion failed: {self._format_error(error)}"
            raise RuntimeError(message) from error

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
            "-crf", str(av1_crf),
        ]

        # At this point the user wants AV1, so add AV1-specific parameters.
        command += ["-b:v", "0"] # Set bitrate to 0 for CRF mode.

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

    @classmethod
    def _format_error(
        cls,
        error: subprocess.CalledProcessError | subprocess.TimeoutExpired,
    ) -> str:
        if isinstance(error, subprocess.TimeoutExpired):
            timeout = cls._format_timeout(error.timeout)
            return f"ffmpeg timed out after {timeout} seconds"

        stderr = cls._format_output(error.stderr)
        if stderr:
            return f"ffmpeg exited with code {error.returncode}: {stderr}"

        return f"ffmpeg exited with code {error.returncode}"

    @staticmethod
    def _format_timeout(timeout: object) -> str:
        if isinstance(timeout, int | float):
            return f"{timeout:g}"
        return str(timeout)

    @staticmethod
    def _format_output(output: object) -> str | None:
        if output is None:
            return None

        if isinstance(output, bytes):
            text = output.decode(errors="replace")
        else:
            text = str(output)

        text = " ".join(text.split())
        if not text:
            return None

        return text[:500]
