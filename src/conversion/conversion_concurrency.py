from dataclasses import dataclass
from threading import BoundedSemaphore

from src.config import Config


def conversion_worker_capacity() -> int:
    options = Config.cli_options
    workers = 0

    if options["convert_to_jxl"]:
        workers += options["jxl_converter_concurrency"]

    if options["video_codec"] == "av1":
        workers += options["av1_converter_concurrency"]

    return max(workers, 1)


@dataclass
class ConversionSlots:
    jxl: BoundedSemaphore
    av1: BoundedSemaphore

    @classmethod
    def from_options(cls) -> "ConversionSlots":
        options = Config.cli_options
        return cls(
            jxl=BoundedSemaphore(options["jxl_converter_concurrency"]),
            av1=BoundedSemaphore(options["av1_converter_concurrency"]),
        )
