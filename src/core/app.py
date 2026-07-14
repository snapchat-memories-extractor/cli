from src.config import Config
from src.conversion.conversion_phase import ConversionPhase
from src.core.state_store import PipelineStateStore
from src.logger import log
from src.metadata.metadata_phase import MetadataPhase
from src.overlay.overlay_phase import OverlayPhase


class App:
    def run(self) -> None:
        state_store = PipelineStateStore()
        self._prepare_state(state_store)

        OverlayPhase(state_store).run()
        MetadataPhase(state_store).run()
        ConversionPhase(state_store).run()

        self._delete_state_if_successful(state_store)

    @staticmethod
    def _delete_state_if_successful(state_store: PipelineStateStore) -> None:
        if not state_store.has_failures():
            state_store.delete()

    @staticmethod
    def _prepare_state(state_store: PipelineStateStore) -> None:
        if Config.cli_options["reset_state"]:
            log("Resetting pipeline state before run.", "info")
            state_store.delete()
        elif Config.cli_options["retry_failed"]:
            state_store.reset_retryable()

        state_store.reset_running()
