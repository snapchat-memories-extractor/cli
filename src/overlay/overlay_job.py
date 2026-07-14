from pathlib import Path

from src.config import Config
from src.helpers import is_video
from src.logger import log
from src.overlay.image_composer import ImageComposer
from src.overlay.scan_overlay_pairs import OverlayPair
from src.overlay.video_composer import VideoComposer


def run_overlay_job(pair: OverlayPair) -> Path:
    mode = Config.cli_options["overlay_mode"]

    output_path = pair.main_path.with_name(
        f"{pair.media_id}-overlaid{pair.main_path.suffix}"
    )

    temp_output = output_path.with_name(
        f"{output_path.stem}.compositing{output_path.suffix}"
    )

    _composite(pair, temp_output)

    if not _is_valid_output(temp_output):
        _log_overlay_failure(pair, temp_output)
        raise RuntimeError("Overlay compositing produced no usable output")

    temp_output.replace(output_path)

    if mode == "on":
        pair.main_path.unlink()

    pair.overlay_path.unlink()
    return output_path


def _composite(pair: OverlayPair, output_path: Path) -> None:
    if is_video(pair.main_path):
        VideoComposer(pair, output_path).apply_overlay()
        return
    
    ImageComposer(pair, output_path).apply_overlay()


def _is_valid_output(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def _log_overlay_failure(pair: OverlayPair, attempted_path: Path) -> None:
    attempted_path.unlink(missing_ok=True)
    log(
        f"Overlay compositing produced no usable output for "
        f"'{pair.media_id}'. Source files were not deleted.",
        "error",
        "OVR",
    )
