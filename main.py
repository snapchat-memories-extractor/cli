from src.config import Config
from src.core.app import App
from src.core.ensure_directories import ensure_directories
from src.core.fail_fast_checks import fail_fast_checks
from src.logger import InitializeLogs, log

if __name__ == "__main__":
    Config.initialize_config()
    InitializeLogs()

    if fail_fast_checks():
        ensure_directories(Config.output_folder, Config.logs_folder)
        log("Application started", "info")

        App().run()

        log("Application finished", "info")
    else:
        log("Application aborted: required paths missing", "critical")
        raise SystemExit(1)
