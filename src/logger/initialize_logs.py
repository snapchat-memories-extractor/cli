import logging
from datetime import UTC, datetime
from pathlib import Path

from src.config import Config
from src.logger.formatter import JSONFormatter


class InitializeLogs:
    def __init__(self) -> None:
        logger = logging.getLogger()
        logger.setLevel(Config.cli_options["log_level"])

        log_path = self._build_log_path()
        self._ensure_log_dir(log_path)
        self._cleanup_old_logs()
        logger.addHandler(self._create_file_handler(log_path))

    def _build_log_path(self) -> Path:
        return Path(Config.logs_folder) / self._create_log_filename()

    def _create_log_filename(self) -> str:
        return f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.jsonl"
    
    @staticmethod
    def _ensure_log_dir(log_path: Path) -> None:
        log_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _cleanup_old_logs() -> None:
        logs_folder = Config.logs_folder
        log_files = sorted(
            (logs_folder.glob("*.jsonl")),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        keep = Config.cli_options["logs_amount"]
        for old_file in log_files[keep - 1 :]:
            old_file.unlink()

    def _create_file_handler(self, path: Path) -> logging.Handler:
        handler = logging.FileHandler(path, encoding="utf-8", delay=True)
        handler.setLevel(Config.cli_options["log_level"])
        handler.setFormatter(JSONFormatter())
        return handler
