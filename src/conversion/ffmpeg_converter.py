import subprocess
from pathlib import Path
from shutil import copy2

from imageio_ffmpeg import get_ffmpeg_exe

from src.config import Config, FFmpegConfig


class VideoConverter:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def run(self) -> Path:
        input_path = self._input_path()
        temp_path = input_path.with_suffix(".tmp" + input_path.suffix)
        timeout = Config.cli_options["ffmpeg_timeout"]

        try:
            if input_path != self.file_path:
                input_path.unlink(missing_ok=True)
                copy2(self.file_path, input_path)
            command = self._build_ffmpeg_command(input_path, temp_path)
            subprocess.run(
                command,
                check=True,
                timeout=timeout,
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
            temp_path.unlink(missing_ok=True)
            self._remove_duplicate(input_path)
            message = f"Video conversion failed: {self._format_error(error)}"
            raise RuntimeError(message) from error
        except OSError as error:
            temp_path.unlink(missing_ok=True)
            self._remove_duplicate(input_path)
            raise RuntimeError(f"Video conversion failed: {error}") from error

        try:
            temp_path.replace(input_path)
        except OSError as error:
            temp_path.unlink(missing_ok=True)
            raise RuntimeError(
                f"Video conversion failed: could not finalize converted video "
                f"{input_path}: {error}"
            ) from error

        return input_path

    def _build_ffmpeg_command(self, input_path: Path, temp_path: Path) -> list[str]:
        codec = FFmpegConfig.get_video_codec()
        av1_crf = Config.cli_options["av1_crf"]

        command = [
            get_ffmpeg_exe(),
            "-y", # Overwrite output files without asking
            "-i", str(input_path),
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

    def _input_path(self) -> Path:
        if not Config.cli_options["keep_conversion_originals"]:
            return self.file_path

        return self.file_path.with_name(
            f"{self.file_path.stem}-av1{self.file_path.suffix}"
        )

    def _remove_duplicate(self, input_path: Path) -> None:
        if input_path == self.file_path:
            return

        input_path.unlink(missing_ok=True)

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
