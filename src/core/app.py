from src.config import Config
from src.conversion.conversion_phase import ConversionPhase
from src.core.state_store import PipelineStateStore
from src.helpers import scan_memory_files, overlay_phase_items
from src.logger import log
from src.metadata.metadata_phase import MetadataPhase
from src.overlay.overlay_phase import OverlayPhase
from src.ui.update_ui import UpdateUI


class App:
    def run(self) -> None:
        state_store = PipelineStateStore()
        ui = UpdateUI(state_store)
        state_store.set_on_change(ui.refresh)
        self._prepare_state(state_store)

        ui.set_phase("overlay", overlay_phase_items())
        OverlayPhase(state_store).run()

        ui.set_phase("metadata", scan_memory_files())
        MetadataPhase(state_store).run()

        ui.set_phase("conversion", scan_memory_files())
        ConversionPhase(state_store).run()

        ui.run("finished", "conversion", scan_memory_files())
        state_store.clear_skipped()

    @staticmethod
    def _prepare_state(state_store: PipelineStateStore) -> None:
        if Config.cli_options["reset_state"]:
            log("Resetting pipeline state before run.", "info")
            state_store.delete()
        elif Config.cli_options["retry_failed"]:
            state_store.reset_retryable()

        state_store.reset_running()

