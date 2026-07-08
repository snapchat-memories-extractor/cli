import subprocess
from pathlib import Path

from imageio_ffmpeg import get_ffmpeg_exe

from src.config import Config
from src.logger import log
from src.memories import Memory


class VideoMetadataWriter:
    def __init__(self, memory: Memory, file_path: Path) -> None:
        self.memory = memory
        self.file_path = file_path

    def write_video_metadata(self) -> Path:
        temporary_video_path = self.file_path.with_suffix(".tmp.mp4")
        command = self._build_ffmpeg_command(temporary_video_path)

        timeout = Config.cli_options["ffmpeg_timeout"]
        ffmpeg_run_result = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

        if ffmpeg_run_result.returncode == 0:
            temporary_video_path.replace(self.file_path)
        else:
            self._log_ffmpeg_failure(ffmpeg_run_result, temporary_video_path)

        return self.file_path

    def _build_ffmpeg_command(self, temporary_video_path: Path) -> list[str]:
        metadata_arguments = self._ffmpeg_metadata_arguments()

        return [
            get_ffmpeg_exe(),
            "-i",
            str(self.file_path),
            "-c",
            "copy",
            *metadata_arguments,
            str(temporary_video_path),
        ]

    def _ffmpeg_metadata_arguments(self) -> list[str]:
        meta_args = ["-metadata", f"creation_time={self.memory.video_creation_time}"]

        if self.memory.location_coords:
            latitude, longitude = self.memory.location_coords
            iso6709 = self._to_iso6709(latitude, longitude)
            self._extend_meta_args(meta_args, latitude, longitude, iso6709)

        return meta_args

    @staticmethod
    def _to_iso6709(lat: float, lon: float) -> str:
        lat_sign = "+" if lat >= 0 else ""
        lon_sign = "+" if lon >= 0 else ""
        return f"{lat_sign}{lat:.6f}{lon_sign}{lon:.6f}/"

    @staticmethod
    def _extend_meta_args(
        args: list[str],
        lat: float,
        lon: float,
        iso6709: str,
    ) -> None:
        args.extend(
            [
                "-metadata",
                f"location={iso6709}",
                "-metadata",
                f"com.apple.quicktime.location.ISO6709={iso6709}",
                "-metadata",
                f"Keys:GPSCoordinates={lat}, {lon}",
            ],
        )

    def _log_ffmpeg_failure(
        self, result: subprocess.CompletedProcess, temp_path: Path
    ) -> None:
        if temp_path.exists():
            temp_path.unlink()
        log(
            f"ffmpeg failed with code {result.returncode} for {self.file_path}",
            "warning",
        )
