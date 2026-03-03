import sqlite3
from pathlib import Path

from storage import Storage


def test_storage_initializes_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "mobile.db"
    storage = Storage(db_path)
    storage.initialize()

    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'").fetchone()
    conn.close()

    assert row is not None


def test_storage_inserts_session(tmp_path: Path) -> None:
    db_path = tmp_path / "mobile.db"
    storage = Storage(db_path)
    storage.initialize()

    session_id = "session-1"
    storage.create_session(
        session_id=session_id,
        device_id="emulator-5554",
        app_id="com.demo.app",
        platform="android",
        trace_id="trace-1",
    )

    sessions = storage.list_sessions(limit=10, cursor=None)
    assert sessions[0]["session_id"] == session_id


def test_storage_retries_on_locked_database(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "mobile.db"
    storage = Storage(db_path)
    storage.initialize()

    real_connect = storage._connect
    state = {"calls": 0}

    def flaky_connect():
        if state["calls"] == 0:
            state["calls"] += 1
            raise sqlite3.OperationalError("database is locked")
        return real_connect()

    monkeypatch.setattr(storage, "_connect", flaky_connect)

    storage.create_session(
        session_id="session-retry",
        device_id="emulator-5554",
        app_id="com.demo.app",
        platform="android",
        trace_id="trace-retry",
    )

    sessions = storage.list_sessions(limit=10, cursor=None)
    assert sessions[0]["session_id"] == "session-retry"
    assert state["calls"] == 1
