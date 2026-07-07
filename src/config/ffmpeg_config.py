from src.config.main import Config


class FFmpegConfig:
    @staticmethod
    def get_video_codec() -> str:
        if Config.cli_options["video_codec"] == "av1":
            if Config.cli_options["av1_encoder"] == "svt-av1":
                return "libsvtav1"
            return "libaom-av1"
        return "libx264"

    @staticmethod
    def get_video_crf() -> str:
        user_crf = Config.cli_options.get("crf", None)
        if user_crf is None:
            return "23" if Config.cli_options["video_codec"] == "h264" else "36"
        return str(user_crf)

    @staticmethod
    def get_video_pixel_format() -> str:
        return Config.cli_options["ffmpeg_pixel_format"]

    @staticmethod
    def get_ffmpeg_preset() -> str:
        return Config.cli_options["ffmpeg_preset"]

    @staticmethod
    def get_av1_speed_params() -> list[str]:
        encoder = Config.cli_options["av1_encoder"]

        if encoder == "svt-av1":
            return ["-svtav1-params", f"preset={Config.cli_options['av1_preset']}"]

        # libaom-av1
        params = [
            "-cpu-used", str(Config.cli_options["av1_cpu_used"]),
            "-tile-columns", str(Config.cli_options["av1_tile_columns"]),
            "-tile-rows", str(Config.cli_options["av1_tile_rows"]),
            "-row-mt", str(Config.cli_options["av1_row_mt"]),
        ]
        return params

    @staticmethod
    def get_av1_quality_params() -> list[str]:
        # Quality tuning flags are libaom-av1 only
        if Config.cli_options["av1_encoder"] != "libaom-av1":
            return []

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

        encoder = Config.cli_options["av1_encoder"]
        grain_denoise = Config.cli_options["grain_denoise"]

        if encoder == "svt-av1":
            svt_params = f"film-grain={film_grain}:film-grain-denoise={grain_denoise}"
            return ["-svtav1-params", svt_params]

        # libaom-av1
        return [
            "-film-grain-table", "",
            "-denoise-noise-level", str(film_grain),
        ]