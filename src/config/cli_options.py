import argparse

from src.config.logging_config import parse_log_level


def build_cli_options(args: argparse.Namespace) -> dict:
    return {
        "memories_json": args.memories_json,
        "max_concurrent_downloads": args.concurrent,
        "apply_overlay": not args.no_overlay,
        "write_metadata": not args.no_metadata,
        "max_attempts": args.attempts,
        "strict_location": args.strict_location,
        "jpeg_quality": args.jpeg_quality,
        "logs_amount": args.logs_amount,
        "convert_to_jxl": not args.no_jxl,
        "log_level": parse_log_level(args.log_level),
        "request_timeout": args.request_timeout,
        "ffmpeg_timeout": args.ffmpeg_timeout,
        "ffmpeg_preset": args.ffmpeg_preset,
        "ffmpeg_pixel_format": args.ffmpeg_pixel_format,
        "video_codec": args.video_codec,
        "crf": args.constant_rate_factor,
        "cjxl_timeout": args.cjxl_timeout,
    }
