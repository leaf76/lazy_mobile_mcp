from pathlib import Path

from errors import WorkerError
from worker import SelectedDevice, Worker


def test_worker_no_active_device_error_uses_request_trace_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "mobile.db"))
    worker = Worker()
    trace_id = "trace-request-001"

    try:
        worker.handle("mobile.screenshot", {}, trace_id)
        assert False, "Expected WorkerError"
    except WorkerError as exc:
        assert exc.code == "ERR_NO_ACTIVE_DEVICE"
        assert exc.trace_id == trace_id


def test_worker_validation_error_uses_request_trace_id(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "mobile.db"))
    worker = Worker()
    worker._selected = SelectedDevice(device_id="emulator-5554", platform="android")
    trace_id = "trace-request-002"

    try:
        worker.handle("mobile.launch_app", {}, trace_id)
        assert False, "Expected WorkerError"
    except WorkerError as exc:
        assert exc.code == "ERR_VALIDATION"
        assert exc.trace_id == trace_id
