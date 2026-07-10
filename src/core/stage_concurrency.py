from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from threading import BoundedSemaphore

INVALID_STAGE_CONCURRENCY = "Stage concurrency must be at least 1"


@dataclass
class StageLimiter:
    max_workers: int
    _semaphore: BoundedSemaphore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise ValueError(INVALID_STAGE_CONCURRENCY)
        self._semaphore = BoundedSemaphore(self.max_workers)

    def slot(self) -> AbstractContextManager[bool | None]:
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

    def conversion_worker_capacity(self, options: dict) -> int:
        active_limits = []
        if options["convert_to_jxl"]:
            active_limits.append(self.jxl_converter.max_workers)
        if options["video_codec"] == "av1":
            active_limits.append(self.av1_converter.max_workers)

        return max(sum(active_limits), 1)

    def overlay_applier_slot(self) -> AbstractContextManager[bool | None]:
        return self.overlay_applier.slot()

    def gps_writer_slot(self) -> AbstractContextManager[bool | None]:
        return self.gps_writer.slot()

    def jxl_converter_slot(self) -> AbstractContextManager[bool | None]:
        return self.jxl_converter.slot()

    def av1_converter_slot(self) -> AbstractContextManager[bool | None]:
        return self.av1_converter.slot()