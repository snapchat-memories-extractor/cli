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
    def get_ffmpeg_preset() -> str:
        return Config.cli_options["ffmpeg_preset"]

    @staticmethod
    def get_video_pixel_format() -> str:
        return Config.cli_options["ffmpeg_pixel_format"]