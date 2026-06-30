import argparse


# Validate CRF value there to escape long help messages
def crf_type(value: str) -> int:
    inavlid_crf_message = "CRF must be between 0 (lossless) and 51 (worst quality)"
    ivalue = int(value)
    if not (0 <= ivalue <= 51):
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
        help="Path to the memories JSON file (default: /data/memories_history.json). Short: -mj",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        metavar="PATH",
        help="Custom output directory for downloaded files (default: ./downloads). Short: -o",
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
        "--ffmpeg-timeout",
        "-f",
        type=int,
        default=60,
        metavar="SECONDS",
        help="Seconds to wait for ffmpeg operations (default: 60). Short: -f",
    )
    parser.add_argument(
        "--request-timeout",
        "-t",
        type=int,
        default=30,
        metavar="SECONDS",
        help="Seconds to wait for HTTP requests (default: 30). Short: -t",
    )
    parser.add_argument(
        "--concurrent",
        "-c",
        type=int,
        default=10,
        metavar="N",
        help="Concurrent downloads (default: 10). Short: -c",
    )
    parser.add_argument(
        "--no-overlay",
        "-O",
        default=False,
        action="store_true",
        help="Skip applying PNG overlay (default: overlay applied). Short: -O",
    )
    parser.add_argument(
        "--no-metadata",
        "-M",
        default=False,
        action="store_true",
        help="Skip writing metadata (default: metadata written). Short: -M",
    )
    parser.add_argument(
        "--attempts",
        "-a",
        type=int,
        default=3,
        metavar="N",
        help="Max retry attempts (default: 3). Short: -a",
    )
    parser.add_argument(
        "--strict",
        "-s",
        default=False,
        dest="strict_location",
        action="store_true",
        help="Fail downloads when location metadata is missing. Short: -s",
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
        choices=["psnr", "ssim", "vmaf_with_preprocessing", "vmaf_without_preprocessing",
                 "vmaf_max_gain", "butteraugli"],
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
        "--constant-rate-factor",
        "--crf",
        type=crf_type,
        default=None,
        help="Constant Rate Factor for video quality \
            (0-51, lower=better, 0=lossless, 18-28 is typical). \
            Defaults to 23 for h264, 36 for av1.",
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
        help=("FFmpeg preset for video encoding (default: fast). Short: -fp"),
    )
    parser.add_argument(
        "--ffmpeg-pixel-format",
        "-pf",
        type=str,
        choices=[
            "yuv420p",
            "rgb24",
            "rgba",
            "nv12",
            "yuv422p",
            "yuv444p",
            "bgr24",
            "gray",
            "yuyv422",
            "p010le",
            "yuv420p10le",
            "nv21",
            "bgra",
            "argb",
        ],
        default="yuv420p",
        help="FFmpeg pixel format for video encoding (default: yuv420p). Short: -pf",
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