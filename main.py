from src.config import Config
from src.logger import LogInitializer, log
from src.pipeline import MemoriesPipeline
from src.ui import StatsManager, UpdateUI


def _fail_fast_checks() -> bool:
    all_paths_ok = True

    if Config.cli_options["write_metadata"] and not Config.json_path.exists():
        log(f"Missing memories JSON file at {Config.json_path}", "error", "MISS")
        all_paths_ok = False

    if not Config.memories_folder.exists():
        log(f"Missing memories folder at {Config.memories_folder}", "error", "MISS")
        all_paths_ok = False

    return all_paths_ok


if __name__ == "__main__":
    Config.initialize_config()
    LogInitializer().configure_logger()
    StatsManager.new_run()

    log("Application started", "info")

    if _fail_fast_checks():
        MemoriesPipeline().run()
    else:
        log("Application aborted: required paths missing", "critical")

    # ------------------------------------------------

    UpdateUI().run("finished")
    log("Application finished", "info")