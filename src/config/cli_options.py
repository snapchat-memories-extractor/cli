import argparse

from src.config.logging_config import parse_log_level


def build_cli_options(args: argparse.Namespace) -> dict:
    return {
        "memories_json": args.memories_json,
        "memories_folder": args.memories_folder,
        "output": args.output,
        "logs_path": args.logs_path,
        "max_concurrent_pairs": args.concurrent,
        "overlay_mode": args.overlay_mode,
        "write_metadata": not args.no_metadata,
        "strict_location": args.strict_location,
        "jpeg_quality": args.jpeg_quality,
        "logs_amount": args.logs_amount,
        "convert_to_jxl": args.jxl,
        "log_level": parse_log_level(args.log_level),
        "ffmpeg_timeout": args.ffmpeg_timeout,
        "ffmpeg_pixel_format": args.ffmpeg_pixel_format,
        "video_codec": args.video_codec,
        "av1_encoder": args.av1_encoder,
        "av1_preset": args.av1_preset,
        "av1_cpu_used": args.av1_cpu_used,
        "av1_tile_columns": args.av1_tile_columns,
        "av1_tile_rows": args.av1_tile_rows,
        "av1_row_mt": args.av1_row_mt,
        "av1_aq_mode": args.av1_aq_mode,
        "av1_lag_in_frames": args.av1_lag_in_frames,
        "av1_tune": args.av1_tune,
        "av1_usage": args.av1_usage,
        "film_grain": args.film_grain,
        "grain_denoise": args.grain_denoise,
        "crf": args.constant_rate_factor,
        "cjxl_timeout": args.cjxl_timeout,
        "ffmpeg_preset": args.ffmpeg_preset,
    }