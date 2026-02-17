import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from imageio_ffmpeg import get_ffmpeg_exe
from PIL import Image

from src.config import Config
from src.config.ffmpeg_config import FFmpegConfig


class VideoComposer:
    def __init__(
        self, video_bytes: bytes, overlay_bytes: bytes, output_path: Path
    ) -> None:
        self.video_bytes = video_bytes
        self.overlay_bytes = overlay_bytes
        self.output_path = output_path

    def apply_overlay(self) -> None:
        # FFMPEG can't read from memory, so we need to write to temp files
        video_temporary_file_path = self._write_video_to_temp_file(".mp4")
        video_width, video_height = self._get_video_dimensions(
            video_temporary_file_path,
        )

        overlay_image = Image.open(BytesIO(self.overlay_bytes))
        # In some cases the overlay image is mismatched by 1 pixel
        overlay_image = self._resize_to_match(
            overlay_image,
            (video_width, video_height),
        )
        overlay_temporary_file_path = self._write_overlay_to_temp_file(overlay_image)

        ffmpeg_command = self._build_ffmpeg_overlay_command(
            video_temporary_file_path,
            overlay_temporary_file_path,
        )
        ffmpeg_timeout = Config.cli_options["ffmpeg_timeout"]
        self._run_ffmpeg_command(ffmpeg_command, ffmpeg_timeout)
        self._cleanup_temp_files(video_temporary_file_path, overlay_temporary_file_path)

    def _write_video_to_temp_file(self, suffix: str) -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(self.video_bytes)
            return temp_file.name

    @staticmethod
    def _get_video_dimensions(video_path: str) -> tuple[int, int]:
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
                video_path,
            ],
            text=True,
        )
        return tuple(map(int, ffprobe_response.strip().split(",")))

    @staticmethod
    def _resize_to_match(
        image: Image.Image,
        target_size: tuple[int, int],
    ) -> Image.Image:
        if image.size != target_size:
            return image.resize(target_size, Image.Resampling.LANCZOS)
        return image

    @staticmethod
    def _write_overlay_to_temp_file(overlay_image: Image.Image) -> str:
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".png",
        ) as overlay_temporary_file:
            overlay_image.save(overlay_temporary_file, format="PNG")
            return overlay_temporary_file.name

    def _build_ffmpeg_overlay_command(
        self, video_path: str, overlay_path: str
    ) -> list[str]:
        return [
            get_ffmpeg_exe(),
            "-i",
            video_path,
            "-i",
            overlay_path,
            "-filter_complex",
            "overlay=0:0",
            "-c:v",
            FFmpegConfig.get_video_codec(),
            "-preset",
            FFmpegConfig.get_ffmpeg_preset(),
            "-crf",
            FFmpegConfig.get_video_crf(),
            "-pix_fmt",
            FFmpegConfig.get_video_pixel_format(),
            "-c:a",
            "copy",
            str(self.output_path),
        ]

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

    @staticmethod
    def _cleanup_temp_files(
        video_temporary_file_path: str,
        overlay_temporary_file_path: str,
    ) -> None:
        Path(video_temporary_file_path).unlink(missing_ok=True)
        Path(overlay_temporary_file_path).unlink(missing_ok=True)
