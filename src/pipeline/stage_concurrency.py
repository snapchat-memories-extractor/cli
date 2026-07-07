from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import BoundedSemaphore


@dataclass
class StageLimiter:
    max_workers: int
    _semaphore: BoundedSemaphore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise ValueError("Stage concurrency must be at least 1")
        self._semaphore = BoundedSemaphore(self.max_workers)

    @contextmanager
    def slot(self) -> Iterator[None]:
        self._semaphore.acquire()
        try:
            yield
        finally:
            self._semaphore.release()


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

    def pair_worker_capacity(self, options: dict) -> int:
        active_limits = []
        if options["overlay_mode"] != "off":
            active_limits.append(self.overlay_applier.max_workers)
        if options["write_metadata"]:
            active_limits.append(self.gps_writer.max_workers)
        if options["convert_to_jxl"]:
            active_limits.append(self.jxl_converter.max_workers)
        if options["video_codec"] == "av1":
            active_limits.append(self.av1_converter.max_workers)

        return max(sum(active_limits), 1)

    @contextmanager
    def overlay_applier_slot(self) -> Iterator[None]:
        with self.overlay_applier.slot():
            yield

    @contextmanager
    def gps_writer_slot(self) -> Iterator[None]:
        with self.gps_writer.slot():
            yield

    @contextmanager
    def jxl_converter_slot(self) -> Iterator[None]:
        with self.jxl_converter.slot():
            yield

    @contextmanager
    def av1_converter_slot(self) -> Iterator[None]:
        with self.av1_converter.slot():
            yield
