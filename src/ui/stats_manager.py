from time import time
from typing import ClassVar


class StatsManager:
    total_files = 0
    start_time = time()

    processed_count = 0
    failed_count = 0
    overlay_applied_count = 0
    matched_count = 0
    unmatched_count = 0
    deleted_unmatched_count = 0

    errors: ClassVar[list[str]] = []

    @classmethod
    def new_run(cls) -> None:
        cls.start_time = time()
        cls.processed_count = 0
        cls.failed_count = 0
        cls.overlay_applied_count = 0
        cls.matched_count = 0
        cls.unmatched_count = 0
        cls.deleted_unmatched_count = 0
        cls.errors = []