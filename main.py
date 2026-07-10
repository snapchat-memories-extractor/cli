from src.config import Config
from src.core.fail_fast_checks import fail_fast_checks
from src.core.app import App
from src.logger import LogInitializer, log
from src.ui import StatsManager, UpdateUI


if __name__ == "__main__":
    Config.initialize_config()
    LogInitializer().configure_logger()
    StatsManager.new_run()

    log("Application started", "info")

    if fail_fast_checks():
        App().run()
    else:
        log("Application aborted: required paths missing", "critical")

    # ------------------------------------------------

    UpdateUI().run("finished")
    log("Application finished", "info")
