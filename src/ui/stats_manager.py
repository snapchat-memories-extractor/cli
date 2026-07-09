from time import time


class StatsManager:
    total_files = 0
    start_time = time()

    processed_count = 0
    failed_count = 0
    matched_count = 0
    unmatched_count = 0

    @classmethod
    def new_run(cls) -> None:
        cls.start_time = time()
        cls.processed_count = 0
        cls.failed_count = 0
        cls.matched_count = 0
        cls.unmatched_count = 0

    @classmethod
    def set_total_files(cls, total_files: int) -> None:
        cls.total_files = total_files

    @classmethod
    def record_processed(cls) -> None:
        cls.processed_count += 1

    @classmethod
    def record_failed(cls) -> None:
        cls.failed_count += 1

    @classmethod
    def record_matched(cls) -> None:
        cls.matched_count += 1

    @classmethod
    def record_unmatched(cls) -> None:
        cls.unmatched_count += 1
