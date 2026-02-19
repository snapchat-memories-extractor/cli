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
        default=5,
        metavar="N",
        help="Concurrent downloads (default: 5). Short: -c",
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
        "--no-jxl",
        "-J",
        default=False,
        action="store_true",
        help="Skip JPGXL conversion and keep original JPEG \
            (default: convert to lossless JPGXL). Short: -J",
    )
    parser.add_argument(
        "--video-codec",
        "-vc",
        type=str,
        choices=["h264", "h265"],
        default="h264",
        help="Choose video codec: h264 (default, best compatibility) or h265 \
            (smaller files, less compatible)",
    )
    parser.add_argument(
        "--constant-rate-factor",
        "--crf",
        type=crf_type,
        default=23,
        help="Constant Rate Factor for video quality \
            (0-51, lower=better, 0=lossless, 18-28 is typical, default: 23)",
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
