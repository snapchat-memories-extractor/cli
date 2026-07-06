import subprocess
import tempfile
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe
from PIL import Image

from src.config import Config
from src.config.ffmpeg_config import FFmpegConfig


class VideoComposer:
    def __init__(self, main_path: Path, overlay_path: Path, output_path: Path) -> None:
        self.main_path = main_path
        self.overlay_path = overlay_path
        self.output_path = output_path

    def apply_overlay(self) -> None:
        video_width, video_height = self._get_video_dimensions(self.main_path)
        overlay_path, temp_overlay_path = self._resolve_overlay_path(
            video_width, video_height
        )

        ffmpeg_command = self._build_ffmpeg_overlay_command(overlay_path)
        ffmpeg_timeout = Config.cli_options["ffmpeg_timeout"]
        self._run_ffmpeg_command(ffmpeg_command, ffmpeg_timeout)

        if temp_overlay_path:
            Path(temp_overlay_path).unlink(missing_ok=True)

    @staticmethod
    def _get_video_dimensions(video_path: Path) -> tuple[int, int]:
        ffprobe_response = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=p=0",
                str(video_path),
            ],
            text=True,
        )
        return tuple(map(int, ffprobe_response.strip().split(",")))

    def _resolve_overlay_path(
        self, width: int, height: int
    ) -> tuple[str, str | None]:
        with Image.open(self.overlay_path) as overlay_image:
            # In some cases the overlay image is mismatched by 1 pixel.
            # Only fall back to a temp file when a resize is actually needed.
            if overlay_image.size == (width, height):
                return str(self.overlay_path), None

            resized = overlay_image.resize((width, height), Image.Resampling.LANCZOS)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                resized.save(tmp, format="PNG")
                return tmp.name, tmp.name

    def _build_ffmpeg_overlay_command(self, overlay_path: str) -> list[str]:
        codec = FFmpegConfig.get_video_codec()
        is_av1 = Config.cli_options["video_codec"] == "av1"

        command = [
            get_ffmpeg_exe(),
            "-i",
            str(self.main_path),
            "-i",
            overlay_path,
            "-filter_complex",
            "overlay=0:0",
            "-map_metadata",
            "0",
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
            "-c:a",
            "copy",
            str(self.output_path),
        ]

        return command

    def _run_ffmpeg_command(
        self, command: list, timeout: int
    ) -> subprocess.CompletedProcess:
        return subprocess.run(
            command,
            check=True,
            timeout=timeout,
            capture_output=True,
            creationflags=self.create_creation_flags(),
        )

    @staticmethod
    def create_creation_flags() -> int:
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            return subprocess.CREATE_NO_WINDOW
        return 0