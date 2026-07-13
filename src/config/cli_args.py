import argparse


# Validate CRF value there to escape long help messages
def crf_type(value: str) -> int:
    inavlid_crf_message = "CRF must be between 0 (lossless) and 63 (worst quality)"
    ivalue = int(value)
    if not (0 <= ivalue <= 63):
        raise argparse.ArgumentTypeError(inavlid_crf_message)
    return ivalue


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
            "(default: ./data/memories_history.json). Short: -mj"
        ),
    )
    parser.add_argument(
        "--memories-folder",
        "-mf",
        type=str,
        default=None,
        metavar="PATH",
        help="Path to the local Snapchat export folder containing \
            <id>-main / <id>-overlay media files (default: ./data/memories). \
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
            "(default: ./downloads). Short: -o"
        ),
    )
    parser.add_argument(
        "--logs-path",
        "-lp",
        type=str,
        default=None,
        metavar="PATH",
        help="Custom directory for log files (default: ./logs). Short: -lp",
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
            "Retry failed pipeline stages and stages skipped by prior failures. "
            "Short: -rf"
        ),
    )
    parser.add_argument(
        "--ffmpeg-timeout",
        "-f",
        type=int,
        default=60,
        metavar="SECONDS",
        help="Seconds to wait for ffmpeg operations (default: 60). Short: -f",
    )
    parser.add_argument(
        "--concurrent",
        "-c",
        type=int,
        default=10,
        metavar="N",
        help="Number of media pairs (main + overlay) to process in parallel \
            (default: 10). This is CPU-bound work Short: -c",
    )
    parser.add_argument(
        "--overlay-mode",
        "-om",
        type=str,
        choices=["on", "off", "both"],
        default="on",
        help="Overlay handling: 'on' composites into a new <id>-overlaid \
            file and deletes both source files. \
            'off' deletes overlay files without compositing them. 'both' \
            composites into a new <id>-overlaid file while keeping the \
            original <id>-main file, and only deletes the overlay source. \
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
        "--gps-writer-concurrency",
        "-gwc",
        type=int,
        choices=range(1, 51),
        default=10,
        metavar="1-50",
        help="Number of GPS metadata write operations to run in parallel \
            (default: 10). Short: -gwc",
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
        default=95,
        metavar="N",
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
        "--video-codec",
        "-vc",
        type=str,
        choices=["h264", "av1"],
        default="h264",
        help="Choose video codec: h264 (default, best compatibility) or av1 \
            (best compression, royalty-free, slower to encode)",
    )
    parser.add_argument(
        "--av1-encoder",
        "-ae",
        type=str,
        choices=["svt-av1", "libaom-av1"],
        default="svt-av1",
        help="AV1 encoder to use when --video-codec=av1: svt-av1 (default, faster) \
            or libaom-av1 (slower, more tuning options). Short: -ae",
    )
    parser.add_argument(
        "--av1-preset",
        "-ap",
        type=int,
        choices=range(0, 14),
        default=8,
        metavar="0-13",
        help="SVT-AV1 encoding speed preset (0=slowest/best, 13=fastest/worst, \
            default: 8). Only applies when --av1-encoder=svt-av1. Short: -ap",
    )
    parser.add_argument(
        "--av1-cpu-used",
        "-acu",
        type=int,
        choices=range(0, 9),
        default=4,
        metavar="0-8",
        help="libaom-av1 encoding speed (0=slowest/best, 8=fastest/worst, \
            default: 4). Only applies when --av1-encoder=libaom-av1. Short: -acu",
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
        help="Enable row-based multi-threading for libaom-av1 (0=disabled, \
            1=enabled, default: 1). Improves encoding speed on multi-core CPUs. \
            Only applies when --av1-encoder=libaom-av1. Short: -arm",
    )
    parser.add_argument(
        "--av1-aq-mode",
        "-aam",
        type=int,
        choices=[0, 1, 2, 3],
        default=0,
        metavar="0-3",
        help="Adaptive quantization mode for libaom-av1: 0=off, 1=variance, \
            2=complexity, 3=cyclic refresh (default: 0). \
            Only applies when --av1-encoder=libaom-av1. Short: -aam",
    )
    parser.add_argument(
        "--av1-lag-in-frames",
        "-alf",
        type=int,
        default=25,
        metavar="N",
        help="Number of frames to look ahead for libaom-av1 rate control \
            (default: 25, max: 35). Higher values improve compression at the \
            cost of memory and latency. \
            Only applies when --av1-encoder=libaom-av1. Short: -alf",
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
        help="Tune libaom-av1 encoding for a specific quality metric \
            (default: none). Only applies when --av1-encoder=libaom-av1. Short: -at",
    )
    parser.add_argument(
        "--av1-usage",
        "-au",
        type=str,
        choices=["good", "realtime", "allintra"],
        default="good",
        help="libaom-av1 usage profile: good (default, best quality/speed tradeoff), \
            realtime (low latency), allintra (still images / intra-only encoding). \
            Only applies when --av1-encoder=libaom-av1. Short: -au",
    )
    parser.add_argument(
        "--film-grain",
        "-fg",
        type=int,
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
        "--constant-rate-factor",
        "--crf",
        type=crf_type,
        default=None,
        help="Constant Rate Factor for video quality (lower=better, 0=lossless). \
            For h264: 0-51, typical range 18-28, default 23. \
            For av1: 0-63, typical range 28-40, default 36.",
    )
    parser.add_argument(
        "--cjxl-timeout",
        "-ct",
        type=int,
        default=120,
        help="Timeout in seconds for cjxl conversion (default: 120). Short: -ct",
    )
    parser.add_argument(
        "--logs-amount",
        "-la",
        type=int,
        default=5,
        help="Number of log files to keep, any log files beyond this number \
            will be deleted (default: 5). Short: -la",
    )
    parser.add_argument(
        "--ffmpeg-preset",
        "-fp",
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
        help="FFmpeg preset for h264 encoding speed (default: fast). \
            Only applies when --video-codec=h264. Short: -fp",
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
        help="Pixel format for video encoding (default: yuv420p). \
            10-bit formats (yuv*10le) require a compatible decoder. \
            Compatible with both h264 and av1. Short: -pf",
    )
    parser.add_argument(
        "--log-level",
        "-l",
        type=str,
        default="OFF",
        metavar="LEVEL",
        help="Logging level: 0=OFF, 1=CRITICAL, 2=ERROR, 3=WARNING, 4=INFO, 5=DEBUG. \
            Can also use names: OFF, CRITICAL, ERROR, WARNING, INFO, DEBUG \
            (default: 0/OFF). Short: -l",
    )
    return parser.parse_args()
