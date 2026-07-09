from src.config import Config
from src.logger import log


def fail_fast_checks() -> bool:
    all_paths_ok = True

    if Config.cli_options["write_metadata"] and not Config.json_path.exists():
        log(f"Missing memories JSON file at {Config.json_path}", "error", "MISS")
        all_paths_ok = False

    if not Config.memories_folder.exists():
        log(f"Missing memories folder at {Config.memories_folder}", "error", "MISS")
        all_paths_ok = False

    return all_paths_ok
