import multiprocessing
from multiprocessing.process import BaseProcess
from multiprocessing.queues import Queue
from pathlib import Path
from queue import Empty

import pylibjxl

from src.config import Config
from src.logger import log


def _convert_jpeg_to_jxl_worker(
    input_path: str,
    output_path: str,
    effort: int,
    result_queue: Queue,
) -> None:
    try:
        pylibjxl.convert_jpeg_to_jxl(
            input_path,
            output_path,
            effort=effort,
        )
    except Exception as error:
        result_queue.put(("error", f"{type(error).__name__}: {error}"))
    else:
        result_queue.put(("ok", ""))


class JXLConverter:
    def __init__(self, input_path: Path) -> None:
        self.input_path = input_path

    def run(self) -> Path | None:
        output_path = self.input_path.with_suffix(".jxl")
        timeout = Config.cli_options["jxl_timeout"]
        effort = Config.cli_options["jxl_effort"]

        try:
            output_path.unlink(missing_ok=True)
            self._run_conversion_process(output_path, timeout, effort)
        except Exception as error:
            self._handle_conversion_failure(output_path, timeout, error)
            return None

        if not output_path.exists():
            log(
                f"pylibjxl did not create output for {self.input_path}",
                "warning",
            )
            return None

        try:
            if self.input_path.exists():
                self.input_path.unlink()
        except OSError as error:
            log(
                f"Could not remove original after JXL conversion "
                f"{self.input_path}: {error}",
                "warning",
            )
        return output_path

    def _handle_conversion_failure(
        self,
        output_path: Path,
        timeout: int,
        error: Exception,
    ) -> None:
        try:
            output_path.unlink(missing_ok=True)
        except OSError as cleanup_error:
            log(
                f"Could not remove partial JXL output {output_path}: "
                f"{cleanup_error}",
                "warning",
            )

        if isinstance(error, TimeoutError):
            log(
                f"pylibjxl timed out after {timeout} seconds converting "
                f"{self.input_path}",
                "warning",
            )
            return

        log(
            f"pylibjxl failed converting {self.input_path}: {error}",
            "warning",
        )

    def _run_conversion_process(
        self,
        output_path: Path,
        timeout: int,
        effort: int,
    ) -> None:
        context = multiprocessing.get_context("spawn")
        result_queue = context.Queue()
        process = context.Process(
            target=_convert_jpeg_to_jxl_worker,
            args=(str(self.input_path), str(output_path), effort, result_queue),
        )
        process.start()
        process.join(timeout)

        if process.is_alive():
            process.terminate()
            process.join()
            raise TimeoutError

        self._raise_worker_error(process, result_queue)

    @staticmethod
    def _raise_worker_error(process: BaseProcess, result_queue: Queue) -> None:
        try:
            status, detail = result_queue.get(timeout=1)
        except Empty:
            if process.exitcode == 0:
                return
            log(
                f"pylibjxl worker exited with code {process.exitcode}",
                "warning",
            )
            raise RuntimeError("JXL conversion worker exited unexpectedly") from None

        if status == "error":
            raise RuntimeError(detail)
