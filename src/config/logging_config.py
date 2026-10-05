import argparse
import logging


def parse_log_level(level_input: str) -> int:
    base_levels = [
        ("0", "OFF", logging.CRITICAL + 10),
        ("1", "CRITICAL", logging.CRITICAL),
        ("2", "ERROR", logging.ERROR),
        ("3", "WARNING", logging.WARNING),
        ("4", "INFO", logging.INFO),
        ("5", "DEBUG", logging.DEBUG),
    ]
    level_map = {}
    for num, name, value in base_levels:
        level_map[num] = value
        level_map[name] = value

    level_upper = level_input.upper()
    if level_upper in level_map:
        return level_map[level_upper]
    error_message = (
        f"Invalid log level: {level_input}. "
        "Use 0-5 or OFF/CRITICAL/ERROR/WARNING/INFO/DEBUG"
    )
    raise argparse.ArgumentTypeError(error_message)
