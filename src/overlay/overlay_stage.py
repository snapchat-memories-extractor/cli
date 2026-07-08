from pathlib import Path

from src.config import Config
from src.logger import log
from src.overlay.image_composer import ImageComposer
from src.overlay.video_composer import VideoComposer
from src.scanner import MediaPair

VIDEO_SUFFIXES = {".mp4"}


class OverlayStage:
    def __init__(self, pair: MediaPair) -> None:
        self.pair = pair

    @staticmethod
    def purge_overlays() -> None:
        deleted = 0
        for overlay_path in Config.memories_folder.rglob("*"):
            # Sanity check: users may add folders even though exports normally do not.
            if overlay_path.is_file() and overlay_path.stem.endswith("-overlay"):
                overlay_path.unlink()
                deleted += 1

        if deleted:
            log(
                f"--overlay-mode=off: deleted {deleted} overlay file(s) "
                "immediately, before processing started.",
                "info",
            )

    def run(self) -> Path | None:
        mode = Config.cli_options["overlay_mode"]

        if mode == "both":
            return self._run_both()
        return self._run_on()

    def _run_on(self) -> Path:
        if not self.pair.overlay_path:
            return self.pair.main_path

        output_path = self.pair.main_path
        temp_output = output_path.with_name(
            f"{output_path.stem}.compositing{output_path.suffix}"
        )

        self._composite(temp_output)

        if not self._is_valid_output(temp_output):
            self._log_overlay_failure(temp_output)
            return self.pair.main_path

        # Only delete sources after the composited output is confirmed good.
        self.pair.main_path.unlink()
        self.pair.overlay_path.unlink()
        temp_output.replace(output_path)
        return output_path

    def _run_both(self) -> Path:
        if not self.pair.overlay_path:
            return self.pair.main_path

        self._warn_both_av1()

        overlaid_path = self.pair.main_path.with_name(
            f"{self.pair.media_id}-overlaid{self.pair.main_path.suffix}"
        )
        temp_output = overlaid_path.with_name(
            f"{overlaid_path.stem}.compositing{overlaid_path.suffix}"
        )

        self._composite(temp_output)

        if not self._is_valid_output(temp_output):
            self._log_overlay_failure(temp_output)
            return self.pair.main_path

        self.pair.overlay_path.unlink()
        temp_output.replace(overlaid_path)
        return overlaid_path

    def _composite(self, output_path: Path) -> None:
        if self.pair.main_path.suffix.lower() in VIDEO_SUFFIXES:
            VideoComposer(self.pair.main_path, self.pair.overlay_path, output_path).apply_overlay()
        else:
            ImageComposer(self.pair.main_path, self.pair.overlay_path, output_path).apply_overlay()

    @staticmethod
    def _is_valid_output(path: Path) -> bool:
        return path.exists() and path.stat().st_size > 0

    def _log_overlay_failure(self, attempted_path: Path) -> None:
        attempted_path.unlink(missing_ok=True)
        log(
            f"Overlay compositing produced no usable output for "
            f"'{self.pair.media_id}'. Sources left untouched.",
            "error",
            "OVR",
        )

    def _warn_both_av1(self) -> None:
        is_video = self.pair.main_path.suffix.lower() in VIDEO_SUFFIXES
        if is_video and Config.cli_options["video_codec"] == "av1":
            log(
                f"--overlay-mode=both with --video-codec=av1 for "
                f"'{self.pair.media_id}' means encoding this file twice "
                "(kept original is untouched, but the new overlaid variant "
                "still needs a full av1 encode).",
                "warning",
            )
