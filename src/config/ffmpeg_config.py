from src.config.main import Config


class FFmpegConfig:
    @staticmethod
    def get_video_codec() -> str:
        if Config.cli_options["video_codec"] == "av1":
            return "libaom-av1"
        return "libx264"

    @staticmethod
    def get_video_pixel_format() -> str:
        return Config.cli_options["ffmpeg_pixel_format"]

    @staticmethod
    def get_av1_speed_params() -> list[str]:
        return [
            "-cpu-used", str(Config.cli_options["av1_cpu_used"]),
            "-tile-columns", str(Config.cli_options["av1_tile_columns"]),
            "-tile-rows", str(Config.cli_options["av1_tile_rows"]),
            "-row-mt", str(Config.cli_options["av1_row_mt"]),
        ]

    @staticmethod
    def get_av1_quality_params() -> list[str]:
        params = [
            "-aq-mode", str(Config.cli_options["av1_aq_mode"]),
            "-lag-in-frames", str(Config.cli_options["av1_lag_in_frames"]),
            "-usage", Config.cli_options["av1_usage"],
        ]

        if Config.cli_options["av1_tune"] is not None:
            params += ["-tune", Config.cli_options["av1_tune"]]

        return params

    @staticmethod
    def get_av1_film_grain_params() -> list[str]:
        film_grain = Config.cli_options["film_grain"]

        if not film_grain:
            return []

        return [
            "-denoise-noise-level", str(film_grain),
            "-aom-params",
            f"enable-dnl-denoising={Config.cli_options['grain_denoise']}",
        ]
