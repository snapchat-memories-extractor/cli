from dataclasses import dataclass, field
from threading import BoundedSemaphore


@dataclass
class StageLimiter:
    max_workers: int
    _semaphore: BoundedSemaphore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._semaphore = BoundedSemaphore(self.max_workers)

    def slot(self) -> BoundedSemaphore:
        return self._semaphore


@dataclass
class StageConcurrency:
    overlay_applier: StageLimiter
    gps_writer: StageLimiter
    jxl_converter: StageLimiter
    av1_converter: StageLimiter

    @classmethod
    def from_options(cls, options: dict) -> "StageConcurrency":
        return cls(
            overlay_applier=StageLimiter(options["overlay_applier_concurrency"]),
            gps_writer=StageLimiter(options["gps_writer_concurrency"]),
            jxl_converter=StageLimiter(options["jxl_converter_concurrency"]),
            av1_converter=StageLimiter(options["av1_converter_concurrency"]),
        )

    # Images and videos share one conversion pool, so combine their capacities.
    def conversion_worker_capacity(self, options: dict) -> int:
        workers = 0

        if options["convert_to_jxl"]:
            workers += self.jxl_converter.max_workers

        if options["video_codec"] == "av1":
            workers += self.av1_converter.max_workers

        return max(workers, 1)

    def overlay_applier_slot(self) -> BoundedSemaphore:
        return self.overlay_applier.slot()

    def gps_writer_slot(self) -> BoundedSemaphore:
        return self.gps_writer.slot()

    def jxl_converter_slot(self) -> BoundedSemaphore:
        return self.jxl_converter.slot()

    def av1_converter_slot(self) -> BoundedSemaphore:
        return self.av1_converter.slot()
