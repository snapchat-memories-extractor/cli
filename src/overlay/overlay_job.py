from pathlib import Path
from shutil import copystat

from src.config import Config
from src.helpers import is_video
from src.logger import log
from src.overlay.image_composer import ImageComposer
from src.overlay.scan_overlay_pairs import OverlayPair
from src.overlay.video_composer import VideoComposer

def run_overlay_job(pair: OverlayPair) -> Path:
    output_path = overlay_output_path(pair)

    temp_output = output_path.with_name(
        f"{output_path.stem}.compositing{output_path.suffix}"
    )

    try:
        _composite(pair, temp_output)
    except Exception:
        temp_output.unlink(missing_ok=True)
        raise

    if not _is_valid_output(temp_output):
        _log_overlay_failure(pair, temp_output)
        raise RuntimeError("Overlay compositing produced no usable output")

    temp_output.replace(output_path)
    copystat(pair.main_path, output_path)
    return output_path


def overlay_output_path(pair: OverlayPair) -> Path:
    return Config.output_folder / f"{pair.media_id}-overlaid{pair.main_path.suffix}"


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
