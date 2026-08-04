import json
import logging
from datetime import UTC, datetime

from src.logger.error_descriptions import ERROR_DESCRIPTIONS


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj = self._get_base_log(record)

        if record.levelno == logging.ERROR:
            log_obj.update(self._get_error_description(record))

        if record.levelno != logging.INFO:
            log_obj.update(self._get_log_context(record))

        return json.dumps(log_obj)

    @staticmethod
    def _get_base_log(record: logging.LogRecord) -> dict:
        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }

    @staticmethod
    def _get_log_context(record: logging.LogRecord) -> dict:
        return {
            "file_path": record.pathname,
            "function": record.funcName,
            "line": record.lineno,
        }

    @staticmethod
    def _get_error_description(record: logging.LogRecord) -> dict:
        code = getattr(record, "error_code", "ERR")
        return {
            "error_code": code,
            "error_message": ERROR_DESCRIPTIONS.get(str(code), "Unexpected error"),
        }
