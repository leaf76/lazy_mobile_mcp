from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class Storage:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._max_lock_retries = 3
        self._retry_base_delay_s = 0.05

    def initialize(self) -> None:
        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    host TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    capabilities_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL,
                    app_id TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    status TEXT NOT NULL,
                    trace_id TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS perf_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    cpu_pct REAL,
                    memory_mb REAL,
                    launch_ms REAL,
                    fps REAL,
                    jank_pct REAL,
                    metric_flags_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    type TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    meta_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    device_id TEXT,
                    created_at TEXT NOT NULL,
                    result_code TEXT NOT NULL
                )
                """
            )

        self._with_connection(operation)

    def upsert_device(
        self,
        *,
        device_id: str,
        platform: str,
        host: str,
        last_seen_at: str,
        capabilities: dict[str, Any],
    ) -> None:
        capabilities_json = json.dumps(capabilities, separators=(",", ":"))
        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO devices(device_id, platform, host, last_seen_at, capabilities_json)
                VALUES(?, ?, ?, ?, ?)
                ON CONFLICT(device_id)
                DO UPDATE SET
                    platform=excluded.platform,
                    host=excluded.host,
                    last_seen_at=excluded.last_seen_at,
                    capabilities_json=excluded.capabilities_json
                """,
                (device_id, platform, host, last_seen_at, capabilities_json),
            )

        self._with_connection(operation)

    def create_session(
        self,
        *,
        session_id: str,
        device_id: str,
        app_id: str,
        platform: str,
        trace_id: str,
        started_at: str | None = None,
    ) -> None:
        effective_started_at = started_at if started_at is not None else datetime_now_utc_iso()
        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO sessions(session_id, device_id, app_id, platform, started_at, ended_at, status, trace_id)
                VALUES(?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (session_id, device_id, app_id, platform, effective_started_at, "running", trace_id),
            )

        self._with_connection(operation)

    def close_session(self, *, session_id: str, ended_at: str, status: str) -> None:
        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                UPDATE sessions
                SET ended_at=?, status=?
                WHERE session_id=?
                """,
                (ended_at, status, session_id),
            )

        self._with_connection(operation)

    def insert_perf_sample(
        self,
        *,
        session_id: str,
        ts: str,
        cpu_pct: float | None,
        memory_mb: float | None,
        launch_ms: float | None,
        fps: float | None,
        jank_pct: float | None,
        metric_flags: dict[str, str],
    ) -> None:
        metric_flags_json = json.dumps(metric_flags, separators=(",", ":"))
        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO perf_samples(session_id, ts, cpu_pct, memory_mb, launch_ms, fps, jank_pct, metric_flags_json)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, ts, cpu_pct, memory_mb, launch_ms, fps, jank_pct, metric_flags_json),
            )

        self._with_connection(operation)

    def insert_artifact(
        self,
        *,
        artifact_id: str,
        session_id: str | None,
        artifact_type: str,
        file_path: str,
        created_at: str,
        meta: dict[str, Any],
    ) -> None:
        meta_json = json.dumps(meta, separators=(",", ":"))
        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO artifacts(artifact_id, session_id, type, file_path, created_at, meta_json)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (artifact_id, session_id, artifact_type, file_path, created_at, meta_json),
            )

        self._with_connection(operation)

    def insert_audit_log(
        self,
        *,
        trace_id: str,
        tool_name: str,
        risk_level: str,
        device_id: str | None,
        created_at: str,
        result_code: str,
    ) -> None:
        def operation(conn: sqlite3.Connection) -> None:
            conn.execute(
                """
                INSERT INTO audit_logs(trace_id, tool_name, risk_level, device_id, created_at, result_code)
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (trace_id, tool_name, risk_level, device_id, created_at, result_code),
            )

        self._with_connection(operation)

    def list_samples(self, *, session_id: str, limit: int, cursor: int) -> tuple[list[dict[str, Any]], int | None]:
        def operation(conn: sqlite3.Connection) -> list[tuple[Any, ...]]:
            return conn.execute(
                """
                SELECT id, ts, cpu_pct, memory_mb, launch_ms, fps, jank_pct, metric_flags_json
                FROM perf_samples
                WHERE session_id = ? AND id > ?
                ORDER BY id ASC
                LIMIT ?
                """,
                (session_id, cursor, limit),
            ).fetchall()

        rows = self._with_connection(operation)

        samples: list[dict[str, Any]] = []
        next_cursor: int | None = None
        for row in rows:
            sample = {
                "id": row[0],
                "ts": row[1],
                "cpu_pct": row[2],
                "memory_mb": row[3],
                "launch_ms": row[4],
                "fps": row[5],
                "jank_pct": row[6],
                "metric_flags": json.loads(row[7]),
            }
            samples.append(sample)
            next_cursor = row[0]

        return samples, next_cursor

    def list_sessions(self, *, limit: int, cursor: str | None) -> list[dict[str, Any]]:
        query = """
        SELECT session_id, device_id, app_id, platform, started_at, ended_at, status, trace_id
        FROM sessions
        """
        params: list[Any] = []
        if cursor is not None:
            query += " WHERE session_id > ?"
            params.append(cursor)
        query += " ORDER BY session_id ASC LIMIT ?"
        params.append(limit)

        def operation(conn: sqlite3.Connection) -> list[tuple[Any, ...]]:
            return conn.execute(query, params).fetchall()

        rows = self._with_connection(operation)

        return [
            {
                "session_id": row[0],
                "device_id": row[1],
                "app_id": row[2],
                "platform": row[3],
                "started_at": row[4],
                "ended_at": row[5],
                "status": row[6],
                "trace_id": row[7],
            }
            for row in rows
        ]

    def _connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path, timeout=5.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _with_connection(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        attempt = 0
        while True:
            try:
                with self._connect() as conn:
                    return operation(conn)
            except sqlite3.OperationalError as exc:
                if not self._is_locked_error(exc) or attempt >= self._max_lock_retries:
                    raise
                time.sleep(self._retry_base_delay_s * (2**attempt))
                attempt += 1

    @staticmethod
    def _is_locked_error(exc: sqlite3.OperationalError) -> bool:
        return "locked" in str(exc).lower()


def datetime_now_utc_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
