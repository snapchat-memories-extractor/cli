from dataclasses import dataclass
from threading import BoundedSemaphore


def conversion_worker_capacity(options: dict) -> int:
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
    def from_options(cls, options: dict) -> "ConversionSlots":
        return cls(
            jxl=BoundedSemaphore(options["jxl_converter_concurrency"]),
            av1=BoundedSemaphore(options["av1_converter_concurrency"]),
        )
