import argparse

from src.config.logging_config import parse_log_level


def _parse_positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error

    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def get_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Snapchat Memories Downloader")
    parser.add_argument(
        "--memories-json",
        "-mj",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Path to the memories JSON file "
            "(default: data/memories_history.json under the project root). "
            "Short: -mj"
        ),
    )
    parser.add_argument(
        "--memories-folder",
        "-mf",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to the local Snapchat export folder containing \
            <id>-main / <id>-overlay media files (default: data/memories/ \
            under the project root). \
            Short: -mf",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Custom output directory for processed files "
            "(default: output/ under the project root). Short: -o"
        ),
    )
    parser.add_argument(
        "--logs-path",
        "-lp",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Custom directory for log files "
            "(default: logs/ under the project root). Short: -lp"
        ),
    )
    parser.add_argument(
        "--reset-state",
        "-rs",
        default=False,
        action="store_true",
        help=(
            "Delete saved pipeline state before processing and start fresh. "
            "Short: -rs"
        ),
    )
    parser.add_argument(
        "--retry-failed",
        "-rf",
        default=False,
        action="store_true",
        help=(
            "Retry failed pipeline stages. "
            "Short: -rf"
        ),
    )
    parser.add_argument(
        "--ffmpeg-timeout",
        "-ft",
        type=_parse_positive_int,
        default=1200,
        metavar="SECONDS",
        help="Seconds to wait for ffmpeg operations (default: 1200). \
            Short: -ft",
    )
    parser.add_argument(
        "--overlay-mode",
        "-om",
        type=str,
        choices=["on", "off", "both"],
        default="on",
        help="Overlay handling: 'on' writes composited <id>-overlaid files. \
            'off' copies clean <id>-main files and ignores overlays. 'both' \
            writes composited <id>-overlaid files and clean <id>-main copies. \
            Source files are left untouched. \
            Short: -om",
    )
    parser.add_argument(
        "--overlay-applier-concurrency",
        "-oac",
        type=int,
        choices=range(1, 51),
        default=10,
        metavar="1-50",
        help="Number of overlay compositing operations to run in parallel \
            (default: 10). Short: -oac",
    )
    parser.add_argument(
        "--overlay-video-crf",
        "-ovc",
        type=int,
        choices=range(0, 52),
        default=18,
        metavar="0-51",
        help="H.264 CRF for video overlay encoding \
            (default: 18). Lower is better; 0 is lossless. Short: -ovc",
    )
    parser.add_argument(
        "--overlay-video-preset",
        "--ffmpeg-preset",
        "-ovp",
        "-fp",
        dest="overlay_video_preset",
        type=str,
        choices=[
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
            "placebo",
        ],
        default="fast",
        help="H.264 preset for video overlay encoding \
            (default: fast). Short: -ovp. Legacy alias: -fp / --ffmpeg-preset",
    )
    parser.add_argument(
        "--overlay-video-pixel-format",
        "-ovpf",
        type=str,
        choices=[
            "yuv420p",
            "yuv422p",
            "yuv444p",
            "yuv420p10le",
            "yuv422p10le",
            "yuv444p10le",
        ],
        default="yuv420p",
        help="Pixel format for video overlay encoding \
            (default: yuv420p). Short: -ovpf",
    )
    parser.add_argument(
        "--metadata-writer-concurrency",
        "-mwc",
        type=int,
        choices=range(1, 51),
        default=10,
        metavar="1-50",
        help="Number of metadata write operations to run in parallel \
            (default: 10). Short: -mwc",
    )
    parser.add_argument(
        "--jxl-converter-concurrency",
        "-jcc",
        type=int,
        choices=range(1, 51),
        default=10,
        metavar="1-50",
        help="Number of JXL conversion operations to run in parallel \
            (default: 10). Ignored unless --jxl is enabled. Short: -jcc",
    )
    parser.add_argument(
        "--av1-converter-concurrency",
        "-acc",
        type=int,
        choices=range(1, 51),
        default=10,
        metavar="1-50",
        help="Number of AV1 conversion operations to run in parallel \
            (default: 10). Ignored unless --video-codec=av1. Short: -acc",
    )
    parser.add_argument(
        "--no-metadata",
        "-M",
        default=False,
        action="store_true",
        help="Skip writing metadata (default: metadata written). Short: -M",
    )
    parser.add_argument(
        "--keep-originals",
        "-ko",
        dest="keep_conversion_originals",
        default=False,
        action="store_true",
        help="Keep original output files alongside converted JXL/AV1 files \
            (default: delete conversion originals). Short: -ko",
    )
    parser.add_argument(
        "--strict",
        "-s",
        default=False,
        dest="strict_location",
        action="store_true",
        help="Permanently delete local media files with no matching \
            location data in the JSON entry. Short: -s",
    )
    parser.add_argument(
        "--jpeg-quality",
        "-q",
        type=int,
        choices=range(1, 101),
        default=95,
        metavar="1-100",
        help="JPEG quality 1-100 (default: 95). Short: -q",
    )
    parser.add_argument(
        "--jxl",
        "-J",
        default=False,
        action="store_true",
        help="Convert JPEG to lossless JPGXL \
            (default: keep original JPEG). Short: -J",
    )
    parser.add_argument(
        "--jxl-effort",
        "-je",
        type=int,
        choices=range(1, 11),
        default=9,
        metavar="1-10",
        help="JPEG XL encoding effort 1-10 (default: 9). Higher values \
            improve compression but are slower. Ignored unless --jxl is enabled. \
            Short: -je",
    )
    parser.add_argument(
        "--video-codec",
        "-vc",
        type=str,
        choices=["h264", "av1"],
        default="h264",
        help="Choose video codec: h264 (default, best compatibility) or av1 \
            (best compression, royalty-free, slower to encode)",
    )
    parser.add_argument(
        "--av1-cpu-used",
        "-acu",
        type=int,
        choices=range(0, 9),
        default=4,
        metavar="0-8",
        help="AV1 encoding speed (0=slowest/best, 8=fastest/worst, \
            default: 4). Only applies when --video-codec=av1. Short: -acu",
    )
    parser.add_argument(
        "--av1-tile-columns",
        "-atc",
        type=int,
        choices=range(0, 7),
        default=0,
        metavar="0-6",
        help="Number of tile columns as log2 value (0=1 tile, 1=2 tiles, \
            2=4 tiles, etc). Improves encoding speed on multi-core CPUs \
            (default: 0). Short: -atc",
    )
    parser.add_argument(
        "--av1-tile-rows",
        "-atr",
        type=int,
        choices=range(0, 7),
        default=0,
        metavar="0-6",
        help="Number of tile rows as log2 value (0=1 tile, 1=2 tiles, \
            2=4 tiles, etc). Improves encoding speed on multi-core CPUs \
            (default: 0). Short: -atr",
    )
    parser.add_argument(
        "--av1-row-mt",
        "-arm",
        type=int,
        choices=[0, 1],
        default=1,
        metavar="0|1",
        help="Enable row-based multi-threading for AV1 (0=disabled, \
            1=enabled, default: 1). Improves encoding speed on multi-core CPUs. \
            Only applies when --video-codec=av1. Short: -arm",
    )
    parser.add_argument(
        "--av1-aq-mode",
        "-aam",
        type=int,
        choices=[0, 1, 2, 3],
        default=0,
        metavar="0-3",
        help="Adaptive quantization mode for AV1: 0=off, 1=variance, \
            2=complexity, 3=cyclic refresh (default: 0). \
            Only applies when --video-codec=av1. Short: -aam",
    )
    parser.add_argument(
        "--av1-lag-in-frames",
        "-alf",
        type=int,
        choices=range(0, 36),
        default=25,
        metavar="0-35",
        help="Number of frames to look ahead for AV1 rate control \
            (default: 25, max: 35). Higher values improve compression at the \
            cost of memory and latency. \
            Only applies when --video-codec=av1. Short: -alf",
    )
    parser.add_argument(
        "--av1-tune",
        "-at",
        type=str,
        choices=[
            "psnr",
            "ssim",
            "vmaf_with_preprocessing",
            "vmaf_without_preprocessing",
            "vmaf_max_gain",
            "butteraugli",
        ],
        default=None,
        metavar="METRIC",
        help="Tune AV1 encoding for a specific quality metric \
            (default: none). Only applies when --video-codec=av1. Short: -at",
    )
    parser.add_argument(
        "--av1-usage",
        "-au",
        type=str,
        choices=["good", "realtime", "allintra"],
        default="good",
        help="AV1 usage profile: good (default, best quality/speed tradeoff), \
            realtime (low latency), allintra (still images / intra-only encoding). \
            Only applies when --video-codec=av1. Short: -au",
    )
    parser.add_argument(
        "--film-grain",
        "-fg",
        type=int,
        choices=range(0, 51),
        default=0,
        metavar="0-50",
        help="Film grain synthesis level for AV1 (0=disabled, 1-50=strength, \
            default: 0). Encodes grain as metadata instead of pixels, \
            improving compression on noisy sources. \
            Only applies when --video-codec=av1. Short: -fg",
    )
    parser.add_argument(
        "--grain-denoise",
        "-gd",
        type=int,
        choices=[0, 1],
        default=1,
        metavar="0|1",
        help="Denoise source before applying film grain synthesis (0=disabled, \
            1=enabled, default: 1). Only applies when --film-grain > 0. Short: -gd",
    )
    parser.add_argument(
        "--av1-crf",
        "--constant-rate-factor",
        "--crf",
        dest="av1_crf",
        type=int,
        choices=range(0, 64),
        default=36,
        metavar="0-63",
        help="AV1 Constant Rate Factor for final video conversion quality \
            (lower=better, 0=lossless; default: 36). Legacy aliases: \
            --crf / --constant-rate-factor.",
    )
    parser.add_argument(
        "--ffmpeg-pixel-format",
        "-pf",
        type=str,
        choices=[
            "yuv420p",
            "yuv422p",
            "yuv444p",
            "yuv420p10le",
            "yuv422p10le",
            "yuv444p10le",
        ],
        default="yuv420p",
        help="Pixel format for final video conversion (default: yuv420p). Short: -pf",
    )
    parser.add_argument(
        "--jxl-timeout",
        "-jt",
        dest="jxl_timeout",
        type=_parse_positive_int,
        default=120,
        metavar="SECONDS",
        help="Timeout in seconds for JXL conversion (default: 120). \
            Short: -jt.",
    )
    parser.add_argument(
        "--logs-amount",
        "-la",
        type=_parse_positive_int,
        default=5,
        metavar="N",
        help="Number of log files to keep, any log files beyond this number \
            will be deleted (default: 5). Short: -la",
    )
    parser.add_argument(
        "--log-level",
        "-l",
        type=parse_log_level,
        default=parse_log_level("OFF"),
        metavar="LEVEL",
        help="Logging level: 0=OFF, 1=CRITICAL, 2=ERROR, 3=WARNING, 4=INFO, 5=DEBUG. \
            Can also use names: OFF, CRITICAL, ERROR, WARNING, INFO, DEBUG \
            (default: 0/OFF). Short: -l",
    )
    return parser.parse_args()
