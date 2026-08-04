from src.config import Config
from src.core.app import App
from src.core.fail_fast_checks import fail_fast_checks
from src.logger import InitializeLogs, log

if __name__ == "__main__":
    Config.initialize_config()
    InitializeLogs()

    if fail_fast_checks():
        log("Application started", "info")

        App().run()

        log("Application finished", "info")
    else:
        log("Application aborted: required paths missing", "critical")
