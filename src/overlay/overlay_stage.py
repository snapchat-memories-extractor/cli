from pathlib import Path

from src.config import Config
from src.helpers import is_video
from src.logger import log
from src.overlay.image_composer import ImageComposer
from src.overlay.scan_overlay_pairs import OverlayPair
from src.overlay.video_composer import VideoComposer

OVERLAY_OUTPUT_FAILED = "Overlay compositing produced no usable output"


def run_overlay_stage(pair: OverlayPair) -> Path:
    mode = Config.cli_options["overlay_mode"]

    if mode == "both":
        return _run_both(pair)
    return _run_on(pair)


def _run_on(pair: OverlayPair) -> Path:
    output_path = pair.main_path
    temp_output = output_path.with_name(
        f"{output_path.stem}.compositing{output_path.suffix}"
    )

    _composite(pair, temp_output)

    if not _is_valid_output(temp_output):
        _log_overlay_failure(pair, temp_output)
        raise RuntimeError(OVERLAY_OUTPUT_FAILED)

    # Only delete sources after the composited output is confirmed good.
    pair.main_path.unlink()
    temp_output.replace(output_path)
    return output_path


def _run_both(pair: OverlayPair) -> Path:
    _warn_both_av1(pair)

    overlaid_path = pair.main_path.with_name(
        f"{pair.media_id}-overlaid{pair.main_path.suffix}"
    )
    temp_output = overlaid_path.with_name(
        f"{overlaid_path.stem}.compositing{overlaid_path.suffix}"
    )

    _composite(pair, temp_output)

    if not _is_valid_output(temp_output):
        _log_overlay_failure(pair, temp_output)
        raise RuntimeError(OVERLAY_OUTPUT_FAILED)

    temp_output.replace(overlaid_path)
    return overlaid_path


def _composite(pair: OverlayPair, output_path: Path) -> None:
    if is_video(pair.main_path):
        VideoComposer(
            pair.main_path,
            pair.overlay_path,
            output_path,
        ).apply_overlay()
    else:
        ImageComposer(
            pair.main_path,
            pair.overlay_path,
            output_path,
        ).apply_overlay()


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


def _warn_both_av1(pair: OverlayPair) -> None:
    if is_video(pair.main_path) and Config.cli_options["video_codec"] == "av1":
        log(
            f"--overlay-mode=both with --video-codec=av1 for "
            f"'{pair.media_id}' means encoding this file twice "
            "(kept original is untouched, but the new overlaid variant "
            "still needs a full av1 encode).",
            "warning",
        )
