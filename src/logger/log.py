import logging
from typing import Literal

APP_LOGGER_NAME = "snapchat_memories_extractor"


def log(
    message: str,
    level: Literal["debug", "info", "warning", "error", "critical"],
    error_code: str | None = None,
) -> None:
    logger = logging.getLogger(APP_LOGGER_NAME)

    if level == "error" and error_code:
        extra = {"error_code": error_code}
        getattr(logger, level)(message, extra=extra, stacklevel=2)
    else:
        getattr(logger, level)(message, stacklevel=2)
