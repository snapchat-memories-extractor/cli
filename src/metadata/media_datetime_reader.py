import subprocess
from datetime import datetime, timezone
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe

from src.config.main import Config
from src.helpers import is_image
from src.logger import log


class MediaDatetimeReader:
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def run(self) -> datetime | None:
        if is_image(self.file_path):
            return self._read_image_datetime()
        return self._read_video_datetime()

    def _read_image_datetime(self) -> datetime | None:
        try:
            # Use modified time because created/accessed times change when memories
            # are copied or extracted between folders.
            return datetime.fromtimestamp(
                self.file_path.stat().st_mtime,
                tz=timezone.utc,
            ).replace(microsecond=0)
        except OSError:
            return None

    def _read_video_datetime(self) -> datetime | None:
        timeout = Config.cli_options["ffmpeg_timeout"]
        try:
            result = subprocess.run(
                [
                    get_ffmpeg_exe(),
                    "-i", str(self.file_path),
                ],
                capture_output=True, # Do not print ffmpeg output to console
                text=True, # Return output as string instead of bytes
                timeout=timeout,
                # Error is handled by checking the return code and stderr output.
                check=False,
            )
        except (subprocess.TimeoutExpired, OSError) as error:
            log(f"ffmpeg failed reading {self.file_path}: {error}", "warning")
            return None

        raw_value = self._extract_creation_time(result.stderr)
        if not raw_value:
            return None

        return self._parse_video_datetime(raw_value)

    @staticmethod
    def _extract_creation_time(ffmpeg_output: str) -> str | None:
        for line in ffmpeg_output.splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip() == "creation_time":
                return value.strip()
        return None

    @staticmethod
    def _parse_video_datetime(raw_value: str) -> datetime | None:
        normalized = raw_value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None

        return (
            parsed.replace(tzinfo=timezone.utc)
            if parsed.tzinfo is None
            else parsed.astimezone(timezone.utc)
        ).replace(microsecond=0)
