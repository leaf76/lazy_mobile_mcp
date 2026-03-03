from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from storage import Storage

SampleFn = Callable[[list[str]], dict[str, float]]


SUPPORTED_METRICS = {"cpu_pct", "memory_mb", "launch_ms", "fps", "jank_pct"}


def normalize_sample(raw_sample: dict[str, float], requested_metrics: list[str]) -> dict[str, object]:
    metric_flags: dict[str, str] = {}
    normalized: dict[str, object] = {
        "cpu_pct": raw_sample.get("cpu_pct"),
        "memory_mb": raw_sample.get("memory_mb"),
        "launch_ms": raw_sample.get("launch_ms"),
        "fps": raw_sample.get("fps"),
        "jank_pct": raw_sample.get("jank_pct"),
    }

    for metric in requested_metrics:
        if metric not in SUPPORTED_METRICS:
            metric_flags[metric] = "unsupported"
            continue

        if normalized.get(metric) is None:
            metric_flags[metric] = "unsupported"
        else:
            metric_flags[metric] = "ok"

    normalized["metric_flags"] = metric_flags
    return normalized


@dataclass
class PerfSessionState:
    stop_event: threading.Event
    worker: threading.Thread
    sample_count: int


class PerfCollector:
    def __init__(self, storage: Storage) -> None:
        self._storage = storage
        self._sessions: dict[str, PerfSessionState] = {}
        self._lock = threading.Lock()

    def start_session(
        self,
        *,
        session_id: str,
        interval_ms: int,
        metrics: list[str],
        sample_fn: SampleFn,
    ) -> None:
        stop_event = threading.Event()

        def worker() -> None:
            while not stop_event.is_set():
                raw_sample = sample_fn(metrics)
                normalized = normalize_sample(raw_sample, metrics)
                ts = datetime.now(timezone.utc).isoformat()
                self._storage.insert_perf_sample(
                    session_id=session_id,
                    ts=ts,
                    cpu_pct=self._to_optional_float(normalized.get("cpu_pct")),
                    memory_mb=self._to_optional_float(normalized.get("memory_mb")),
                    launch_ms=self._to_optional_float(normalized.get("launch_ms")),
                    fps=self._to_optional_float(normalized.get("fps")),
                    jank_pct=self._to_optional_float(normalized.get("jank_pct")),
                    metric_flags=normalized["metric_flags"],
                )
                with self._lock:
                    self._sessions[session_id].sample_count += 1

                stop_event.wait(interval_ms / 1000)

        thread = threading.Thread(target=worker, daemon=True)
        state = PerfSessionState(stop_event=stop_event, worker=thread, sample_count=0)
        with self._lock:
            self._sessions[session_id] = state
        thread.start()

    def stop_session(self, *, session_id: str) -> int:
        with self._lock:
            state = self._sessions.get(session_id)

        if state is None:
            return 0

        state.stop_event.set()
        state.worker.join(timeout=3)

        with self._lock:
            sample_count = state.sample_count
            self._sessions.pop(session_id, None)

        return sample_count

    @staticmethod
    def _to_optional_float(value: object) -> float | None:
        if isinstance(value, (float, int)):
            return float(value)
        return None
