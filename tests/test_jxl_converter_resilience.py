from __future__ import annotations

from pathlib import Path
from queue import Empty

import pytest

from src.conversion import jxl_converter
from src.conversion.jxl_converter import JXLConverter, _convert_jpeg_to_jxl_worker


class RecordingQueue:
    def __init__(self, response: tuple[str, str] | Exception | None = None) -> None:
        self.items: list[tuple[str, str]] = []
        self.response = response

    def put(self, item: tuple[str, str]) -> None:
        self.items.append(item)

    def get(self, timeout: int) -> tuple[str, str]:
        assert timeout == 1
        if isinstance(self.response, Exception):
            raise self.response
        if self.response is not None:
            return self.response
        raise Empty


def test_jxl_worker_reports_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, int]] = []
    queue = RecordingQueue()

    def fake_convert(input_path: str, output_path: str, effort: int) -> None:
        calls.append((input_path, output_path, effort))

    monkeypatch.setattr(jxl_converter.pylibjxl, "convert_jpeg_to_jxl", fake_convert)

    _convert_jpeg_to_jxl_worker("in.jpg", "out.jxl", 7, queue)

    assert calls == [("in.jpg", "out.jxl", 7)]
    assert queue.items == [("ok", "")]


def test_jxl_worker_reports_exception_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    queue = RecordingQueue()

    def fake_convert(_input_path: str, _output_path: str, effort: int) -> None:
        assert effort == 7
        error_message = "not a jpeg"
        raise ValueError(error_message)

    monkeypatch.setattr(jxl_converter.pylibjxl, "convert_jpeg_to_jxl", fake_convert)

    _convert_jpeg_to_jxl_worker("in.jpg", "out.jxl", 7, queue)

    assert queue.items == [("error", "ValueError: not a jpeg")]


def test_jxl_converter_run_success_removes_original(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "photo.jpg"
    source.write_bytes(b"jpeg")

    def fake_run_process(self: JXLConverter, output_path: Path, *_args: object) -> None:
        assert self.input_path == source
        output_path.write_bytes(b"jxl")

    monkeypatch.setattr(JXLConverter, "_run_conversion_process", fake_run_process)

    output = JXLConverter(source).run()

    assert output == tmp_path / "photo.jxl"
    assert output.read_bytes() == b"jxl"
    assert not source.exists()


def test_jxl_converter_run_succeeds_when_original_is_already_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "photo.jpg"

    def fake_run_process(
        _self: JXLConverter,
        output_path: Path,
        *_args: object,
    ) -> None:
        output_path.write_bytes(b"jxl")

    monkeypatch.setattr(JXLConverter, "_run_conversion_process", fake_run_process)

    output = JXLConverter(source).run()

    assert output == tmp_path / "photo.jxl"
    assert output.read_bytes() == b"jxl"


def test_jxl_converter_run_keeps_output_when_original_delete_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "photo.jpg"
    source.write_bytes(b"jpeg")
    original_unlink = Path.unlink

    def fake_run_process(
        _self: JXLConverter,
        output_path: Path,
        *_args: object,
    ) -> None:
        output_path.write_bytes(b"jxl")

    def fake_unlink(self: Path, missing_ok: bool = False) -> None:
        if self == source:
            raise OSError
        original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(JXLConverter, "_run_conversion_process", fake_run_process)
    monkeypatch.setattr(Path, "unlink", fake_unlink)

    output = JXLConverter(source).run()

    assert output == tmp_path / "photo.jxl"
    assert output.read_bytes() == b"jxl"
    assert source.exists()


def test_jxl_converter_run_returns_none_when_worker_creates_no_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "photo.jpg"
    source.write_bytes(b"jpeg")
    monkeypatch.setattr(
        JXLConverter,
        "_run_conversion_process",
        lambda *_args: None,
    )

    assert JXLConverter(source).run() is None
    assert source.exists()


def test_jxl_converter_run_cleans_partial_output_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "photo.jpg"
    output = tmp_path / "photo.jxl"
    source.write_bytes(b"jpeg")
    output.write_bytes(b"partial")

    def fake_run_process(_self: JXLConverter, _path: Path, *_args: object) -> None:
        error_message = "encoder failed"
        raise RuntimeError(error_message)

    monkeypatch.setattr(JXLConverter, "_run_conversion_process", fake_run_process)

    assert JXLConverter(source).run() is None
    assert source.exists()
    assert not output.exists()


def test_jxl_converter_handles_timeout_failure_without_leaving_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "photo.jpg"
    output = tmp_path / "photo.jxl"
    source.write_bytes(b"jpeg")
    output.write_bytes(b"partial")

    JXLConverter(source)._handle_conversion_failure(output, 5, TimeoutError())

    assert not output.exists()


def test_jxl_converter_handles_partial_output_cleanup_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "photo.jpg"
    output = tmp_path / "photo.jxl"
    source.write_bytes(b"jpeg")
    output.write_bytes(b"partial")
    original_unlink = Path.unlink

    def fake_unlink(self: Path, missing_ok: bool = False) -> None:
        if self == output:
            raise OSError
        original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fake_unlink)

    JXLConverter(source)._handle_conversion_failure(
        output,
        5,
        RuntimeError(),
    )

    assert output.exists()


def test_jxl_converter_run_conversion_process_times_out(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    process = FakeProcess(alive=True)
    context = FakeContext(process, RecordingQueue())
    monkeypatch.setattr(jxl_converter.multiprocessing, "get_context", lambda _: context)

    with pytest.raises(TimeoutError):
        JXLConverter(tmp_path / "photo.jpg")._run_conversion_process(
            tmp_path / "photo.jxl",
            timeout=3,
            effort=8,
        )

    assert process.started
    assert process.terminated
    assert process.join_calls == [3, None]


def test_jxl_converter_run_conversion_process_raises_worker_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    process = FakeProcess(alive=False, exitcode=1)
    context = FakeContext(process, RecordingQueue())
    monkeypatch.setattr(jxl_converter.multiprocessing, "get_context", lambda _: context)

    with pytest.raises(RuntimeError, match="unexpectedly"):
        JXLConverter(tmp_path / "photo.jpg")._run_conversion_process(
            tmp_path / "photo.jxl",
            timeout=3,
            effort=8,
        )

    assert process.started


def test_jxl_converter_raise_worker_error_accepts_clean_empty_queue() -> None:
    JXLConverter._raise_worker_error(
        FakeProcess(alive=False, exitcode=0),
        RecordingQueue(),
    )


def test_jxl_converter_raise_worker_error_raises_reported_error() -> None:
    with pytest.raises(RuntimeError, match="ValueError: broken"):
        JXLConverter._raise_worker_error(
            FakeProcess(alive=False, exitcode=0),
            RecordingQueue(("error", "ValueError: broken")),
        )


def test_jxl_converter_raise_worker_error_accepts_reported_success() -> None:
    JXLConverter._raise_worker_error(
        FakeProcess(alive=False, exitcode=0),
        RecordingQueue(("ok", "")),
    )


class FakeProcess:
    def __init__(self, *, alive: bool, exitcode: int | None = 0) -> None:
        self._alive = alive
        self.exitcode = exitcode
        self.started = False
        self.terminated = False
        self.join_calls: list[int | None] = []

    def start(self) -> None:
        self.started = True

    def join(self, timeout: int | None = None) -> None:
        self.join_calls.append(timeout)

    def is_alive(self) -> bool:
        return self._alive

    def terminate(self) -> None:
        self.terminated = True
        self._alive = False


class FakeContext:
    def __init__(self, process: FakeProcess, queue: RecordingQueue) -> None:
        self.process = process
        self.queue = queue
        self.process_args: tuple[object, ...] | None = None

    def Queue(self) -> RecordingQueue:  # noqa: N802
        return self.queue

    def Process(  # noqa: N802
        self,
        *,
        target: object,
        args: tuple[object, ...],
    ) -> FakeProcess:
        assert target is _convert_jpeg_to_jxl_worker
        assert args[-1] is self.queue
        self.process_args = args
        return self.process
