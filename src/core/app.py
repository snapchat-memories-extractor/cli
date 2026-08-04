from src.config import Config
from src.conversion.conversion_phase import ConversionPhase
from src.core.state_store import StateStore
from src.helpers import overlay_phase_items, scan_output_files
from src.logger import log
from src.metadata.metadata_phase import MetadataPhase
from src.overlay.overlay_phase import OverlayPhase
from src.ui.update_ui import UpdateUI


class App:
    def run(self) -> None:
        state_store = StateStore()
        ui = UpdateUI(state_store)
        state_store.set_on_change(ui.refresh)
        self._prepare_state(state_store)

        ui.set_phase("overlay", overlay_phase_items())
        OverlayPhase(state_store).run()

        ui.set_phase("metadata", scan_output_files())
        MetadataPhase(state_store).run()

        ui.set_phase("conversion", scan_output_files())
        ConversionPhase(state_store).run()

        ui.run("finished", "conversion", scan_output_files())
        state_store.clear_skipped()

    @staticmethod
    def _prepare_state(state_store: StateStore) -> None:
        if Config.cli_options["reset_state"]:
            log("Resetting pipeline state before run.", "info")
            state_store.delete()
        elif Config.cli_options["retry_failed"]:
            state_store.reset_retryable()

        state_store.reset_running()
