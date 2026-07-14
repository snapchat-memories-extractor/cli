import subprocess
import tempfile
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe, read_frames
from PIL import Image

from src.config import Config
from src.overlay.scan_overlay_pairs import OverlayPair


class VideoComposer:
    def __init__(self, pair: OverlayPair, output_path: Path) -> None:
        self.main_path = pair.main_path
        self.overlay_path = pair.overlay_path
        self.output_path = output_path

    def apply_overlay(self) -> None:
        video_width, video_height = self._get_video_dimensions(self.main_path)
        overlay_path = self._resolve_overlay_path(video_width, video_height)

        try:
            ffmpeg_command = self._build_ffmpeg_overlay_command(overlay_path)
            self._run_ffmpeg_command(ffmpeg_command)
        finally:
            # Clean up the temporary overlay file if it was created
            if overlay_path != self.overlay_path:
                overlay_path.unlink(missing_ok=True)

    @staticmethod
    def _get_video_dimensions(video_path: Path) -> tuple[int, int]:
        reader = read_frames(video_path)
        try:
            metadata = next(reader)
        finally:
            reader.close()

        width, height = metadata["source_size"]
        return int(width), int(height)

    def _resolve_overlay_path(self, width: int, height: int) -> Path:
        with Image.open(self.overlay_path) as overlay_image:
            # In some cases the overlay image is mismatched by 1 pixel.
            # Only fall back to a temp file when a resize is actually needed.
            if overlay_image.size == (width, height):
                return self.overlay_path

            resized = overlay_image.resize((width, height), Image.Resampling.LANCZOS)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                resized.save(tmp, format="PNG")
                return Path(tmp.name)

    def _build_ffmpeg_overlay_command(self, overlay_path: Path) -> list[str]:
        crf = Config.cli_options["overlay_video_crf"]
        preset = Config.cli_options["overlay_video_preset"]
        pixel_format = Config.cli_options["overlay_video_pixel_format"]

        return [
            get_ffmpeg_exe(),
            "-i", str(self.main_path),
            "-i", str(overlay_path),
            "-filter_complex", "overlay=0:0", # Overlay at top-left corner
            "-map_metadata", "0", # Preserve metadata from the main video
            "-c:v", "libx264", # Use H.264 codec for video encoding
            "-crf", str(crf),
            "-preset", preset,
            "-pix_fmt", pixel_format,
            "-c:a", "copy", # Copy audio stream without re-encoding
            str(self.output_path),
        ]

    def _run_ffmpeg_command(self, command: list) -> subprocess.CompletedProcess:
        timeout = Config.cli_options["ffmpeg_timeout"]

        return subprocess.run(
            command,
            check=True, # Raise error if ffmpeg fails
            timeout=timeout,
            capture_output=True, # Do not print ffmpeg output to console
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), # Prevents opening a new console window on Windows
        )
