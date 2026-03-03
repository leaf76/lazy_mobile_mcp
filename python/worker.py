from __future__ import annotations

import json
import os
import platform
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from adapters.android_adapter import AndroidAdapter
from adapters.ios_adapter import IOSAdapter
from errors import WorkerError, error_response
from perf_collector import PerfCollector
from policy_guard import PolicyError, PolicyGuard
from storage import Storage


@dataclass
class SelectedDevice:
    device_id: str
    platform: str
    target_type: str | None = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def json_log(level: str, event: str, payload: dict[str, Any]) -> None:
    log_line = {
        "ts": utc_now_iso(),
        "level": level,
        "event": event,
        **payload,
    }
    sys.stderr.write(json.dumps(log_line, separators=(",", ":")) + "\n")
    sys.stderr.flush()


class Worker:
    def __init__(self) -> None:
        sqlite_path = Path(os.environ.get("SQLITE_PATH", "artifacts/mobile.db"))
        self._storage = Storage(sqlite_path)
        self._storage.initialize()

        allowlist = set(
            part.strip()
            for part in os.environ.get("DEVICE_ALLOWLIST", "").split(",")
            if part.strip()
        )
        high_risk = set(
            part.strip()
            for part in os.environ.get("HIGH_RISK_TOOLS", "mobile.factory_reset,mobile.uninstall_app,mobile.reboot").split(",")
            if part.strip()
        )
        self._policy_guard = PolicyGuard(allowlist=allowlist, high_risk_tools=high_risk)

        self._android = AndroidAdapter(adb_bin=os.environ.get("ADB_BIN", "adb"))
        self._ios = IOSAdapter(wda_base_url=os.environ.get("WDA_BASE_URL"))
        self._perf = PerfCollector(self._storage)
        self._selected: SelectedDevice | None = None

    def handle(self, method: str, params: dict[str, Any], trace_id: str) -> dict[str, Any]:
        self._policy_guard.assert_tool_risk(method, params)

        if method == "mobile.list_devices":
            return self._list_devices(params, trace_id)
        if method == "mobile.select_device":
            return self._select_device(params, trace_id)
        if method == "mobile.get_capabilities":
            return self._get_capabilities(params, trace_id)
        if method == "mobile.screenshot":
            return self._screenshot(params, trace_id)
        if method == "mobile.tap":
            return self._tap(params, trace_id)
        if method == "mobile.swipe":
            return self._swipe(params, trace_id)
        if method == "mobile.input_text":
            return self._input_text(params, trace_id)
        if method == "mobile.launch_app":
            return self._launch_app(params, trace_id)
        if method == "mobile.stop_app":
            return self._stop_app(params, trace_id)
        if method == "mobile.start_perf_session":
            return self._start_perf_session(params, trace_id)
        if method == "mobile.stop_perf_session":
            return self._stop_perf_session(params, trace_id)
        if method == "mobile.get_perf_samples":
            return self._get_perf_samples(params, trace_id)

        raise WorkerError(
            message=f"Unsupported tool method: {method}",
            code="ERR_UNSUPPORTED_TOOL",
            category="validation",
            trace_id=trace_id,
        )

    def _list_devices(self, params: dict[str, Any], trace_id: str) -> dict[str, Any]:
        target = str(params.get("platform", "all"))
        devices: list[dict[str, Any]] = []

        if target in {"android", "all"}:
            devices.extend(self._android.list_devices())

        if target in {"ios", "all"}:
            ios_devices = self._ios.list_devices()
            if target == "ios" and len(ios_devices) == 0 and not self._ios.is_supported_host:
                raise WorkerError(
                    message="iOS control requires macOS host",
                    code="ERR_IOS_UNAVAILABLE_ON_HOST",
                    category="dependency",
                    trace_id=trace_id,
                )
            devices.extend(ios_devices)

        return {"devices": devices}

    def _select_device(self, params: dict[str, Any], trace_id: str) -> dict[str, Any]:
        device_id = str(params.get("device_id", "")).strip()
        if len(device_id) == 0:
            raise WorkerError(
                message="device_id is required",
                code="ERR_VALIDATION",
                category="validation",
                trace_id=trace_id,
            )

        self._policy_guard.assert_device_allowed(device_id)

        all_devices = self._list_devices({"platform": "all"}, trace_id)["devices"]
        matched = next((item for item in all_devices if item.get("device_id") == device_id), None)
        if matched is None:
            raise WorkerError(
                message=f"Device not found: {device_id}",
                code="ERR_DEVICE_NOT_FOUND",
                category="business",
                trace_id=trace_id,
            )

        selected = SelectedDevice(
            device_id=device_id,
            platform=str(matched["platform"]),
            target_type=str(matched.get("target_type")) if matched.get("target_type") is not None else None,
        )
        self._selected = selected

        self._storage.upsert_device(
            device_id=selected.device_id,
            platform=selected.platform,
            host=platform.node(),
            last_seen_at=utc_now_iso(),
            capabilities=matched.get("capabilities", {}),
        )

        return {
            "selected_device": {
                "device_id": selected.device_id,
                "platform": selected.platform,
                "target_type": selected.target_type,
            }
        }

    def _get_capabilities(self, params: dict[str, Any], trace_id: str) -> dict[str, Any]:
        selected = self._resolve_device(params, trace_id)
        if selected.platform == "android":
            capabilities = self._android.get_capabilities()
        else:
            capabilities = self._ios.get_capabilities(device_id=selected.device_id)

        return capabilities

    def _screenshot(self, params: dict[str, Any], trace_id: str) -> dict[str, Any]:
        selected = self._resolve_device(params, trace_id)
        artifact_id = str(uuid4())
        output_path = Path("artifacts/screenshots") / f"{artifact_id}.png"

        if selected.platform == "android":
            result = self._android.screenshot(device_id=selected.device_id, output_path=output_path)
        else:
            if not self._ios.is_supported_host:
                raise WorkerError(
                    message="iOS control requires macOS host",
                    code="ERR_IOS_UNAVAILABLE_ON_HOST",
                    category="dependency",
                    trace_id=trace_id,
                )
            result = self._ios.screenshot(device_id=selected.device_id, output_path=output_path)

        self._storage.insert_artifact(
            artifact_id=artifact_id,
            session_id=None,
            artifact_type="screenshot",
            file_path=result["path"],
            created_at=utc_now_iso(),
            meta={
                "width": result.get("width", 0),
                "height": result.get("height", 0),
                "device_id": selected.device_id,
                "platform": selected.platform,
            },
        )

        return {
            "artifact_id": artifact_id,
            "path": result["path"],
            "width": result.get("width", 0),
            "height": result.get("height", 0),
        }

    def _tap(self, params: dict[str, Any], trace_id: str) -> dict[str, Any]:
        selected = self._resolve_device(params, trace_id)
        x = int(params.get("x", 0))
        y = int(params.get("y", 0))

        if selected.platform == "android":
            self._android.tap(device_id=selected.device_id, x=x, y=y)
        else:
            if not self._ios.is_supported_host:
                raise WorkerError(
                    message="iOS control requires macOS host",
                    code="ERR_IOS_UNAVAILABLE_ON_HOST",
                    category="dependency",
                    trace_id=trace_id,
                )
            self._ios.tap(device_id=selected.device_id, x=x, y=y)

        return {"ok": True}

    def _swipe(self, params: dict[str, Any], trace_id: str) -> dict[str, Any]:
        selected = self._resolve_device(params, trace_id)
        x1 = int(params.get("x1", 0))
        y1 = int(params.get("y1", 0))
        x2 = int(params.get("x2", 0))
        y2 = int(params.get("y2", 0))
        duration_ms = int(params.get("duration_ms", 300))

        if selected.platform == "android":
            self._android.swipe(
                device_id=selected.device_id,
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                duration_ms=duration_ms,
            )
        else:
            if not self._ios.is_supported_host:
                raise WorkerError(
                    message="iOS control requires macOS host",
                    code="ERR_IOS_UNAVAILABLE_ON_HOST",
                    category="dependency",
                    trace_id=trace_id,
                )
            self._ios.swipe(device_id=selected.device_id, x1=x1, y1=y1, x2=x2, y2=y2, duration_ms=duration_ms)

        return {"ok": True}

    def _input_text(self, params: dict[str, Any], trace_id: str) -> dict[str, Any]:
        selected = self._resolve_device(params, trace_id)
        text = str(params.get("text", ""))

        if selected.platform == "android":
            self._android.input_text(device_id=selected.device_id, text=text)
        else:
            if not self._ios.is_supported_host:
                raise WorkerError(
                    message="iOS control requires macOS host",
                    code="ERR_IOS_UNAVAILABLE_ON_HOST",
                    category="dependency",
                    trace_id=trace_id,
                )
            self._ios.input_text(device_id=selected.device_id, text=text)

        return {"ok": True}

    def _launch_app(self, params: dict[str, Any], trace_id: str) -> dict[str, Any]:
        selected = self._resolve_device(params, trace_id)
        app_id = str(params.get("app_id", "")).strip()
        if len(app_id) == 0:
            raise WorkerError(
                message="app_id is required",
                code="ERR_VALIDATION",
                category="validation",
                trace_id=trace_id,
            )

        if selected.platform == "android":
            result = self._android.launch_app(device_id=selected.device_id, app_id=app_id)
        else:
            if not self._ios.is_supported_host:
                raise WorkerError(
                    message="iOS control requires macOS host",
                    code="ERR_IOS_UNAVAILABLE_ON_HOST",
                    category="dependency",
                    trace_id=trace_id,
                )
            result = self._ios.launch_app(device_id=selected.device_id, app_id=app_id)

        return {
            "ok": True,
            "launch_ms": result.get("launch_ms"),
        }

    def _stop_app(self, params: dict[str, Any], trace_id: str) -> dict[str, Any]:
        selected = self._resolve_device(params, trace_id)
        app_id = str(params.get("app_id", "")).strip()
        if len(app_id) == 0:
            raise WorkerError(
                message="app_id is required",
                code="ERR_VALIDATION",
                category="validation",
                trace_id=trace_id,
            )

        if selected.platform == "android":
            self._android.stop_app(device_id=selected.device_id, app_id=app_id)
        else:
            if not self._ios.is_supported_host:
                raise WorkerError(
                    message="iOS control requires macOS host",
                    code="ERR_IOS_UNAVAILABLE_ON_HOST",
                    category="dependency",
                    trace_id=trace_id,
                )
            self._ios.stop_app(device_id=selected.device_id, app_id=app_id)

        return {"ok": True}

    def _start_perf_session(self, params: dict[str, Any], trace_id: str) -> dict[str, Any]:
        selected = self._resolve_device(params, trace_id)
        app_id = str(params.get("app_id", "")).strip()
        if len(app_id) == 0:
            raise WorkerError(
                message="app_id is required",
                code="ERR_VALIDATION",
                category="validation",
                trace_id=trace_id,
            )

        interval_ms = int(params.get("interval_ms", 1000))
        metrics = [str(item) for item in params.get("metrics", ["cpu_pct", "memory_mb", "launch_ms"])]

        session_id = str(uuid4())
        started_at = utc_now_iso()
        self._storage.create_session(
            session_id=session_id,
            device_id=selected.device_id,
            app_id=app_id,
            platform=selected.platform,
            trace_id=trace_id,
            started_at=started_at,
        )

        def sample_fn(requested_metrics: list[str]) -> dict[str, float]:
            if selected.platform == "android":
                return self._android.collect_metrics(device_id=selected.device_id, app_id=app_id, metrics=requested_metrics)
            return self._ios.collect_metrics(device_id=selected.device_id, app_id=app_id, metrics=requested_metrics)

        self._perf.start_session(
            session_id=session_id,
            interval_ms=interval_ms,
            metrics=metrics,
            sample_fn=sample_fn,
        )

        return {
            "session_id": session_id,
            "started_at": started_at,
        }

    def _stop_perf_session(self, params: dict[str, Any], trace_id: str) -> dict[str, Any]:
        session_id = str(params.get("session_id", "")).strip()
        if len(session_id) == 0:
            raise WorkerError(
                message="session_id is required",
                code="ERR_VALIDATION",
                category="validation",
                trace_id=trace_id,
            )

        sample_count = self._perf.stop_session(session_id=session_id)
        ended_at = utc_now_iso()
        self._storage.close_session(session_id=session_id, ended_at=ended_at, status="stopped")

        return {
            "sample_count": sample_count,
            "summary": {
                "session_id": session_id,
                "ended_at": ended_at,
            },
        }

    def _get_perf_samples(self, params: dict[str, Any], trace_id: str) -> dict[str, Any]:
        session_id = str(params.get("session_id", "")).strip()
        limit = int(params.get("limit", 100))
        cursor = int(params.get("cursor", 0))

        samples, next_cursor = self._storage.list_samples(session_id=session_id, limit=limit, cursor=cursor)
        return {
            "samples": samples,
            "next_cursor": next_cursor,
        }

    def _resolve_device(self, params: dict[str, Any], trace_id: str) -> SelectedDevice:
        requested = params.get("device_id")
        if isinstance(requested, str) and len(requested.strip()) > 0:
            self._policy_guard.assert_device_allowed(requested)
            devices = self._list_devices({"platform": "all"}, trace_id)["devices"]
            matched = next((item for item in devices if item.get("device_id") == requested), None)
            if matched is None:
                raise WorkerError(
                    message=f"Device not found: {requested}",
                    code="ERR_DEVICE_NOT_FOUND",
                    category="business",
                    trace_id=trace_id,
                )
            return SelectedDevice(
                device_id=requested,
                platform=str(matched["platform"]),
                target_type=str(matched.get("target_type")) if matched.get("target_type") is not None else None,
            )

        if self._selected is not None:
            return self._selected

        raise WorkerError(
            message="No selected device; call mobile.select_device first or pass device_id",
            code="ERR_NO_ACTIVE_DEVICE",
            category="business",
            trace_id=trace_id,
        )


def main() -> None:
    worker = Worker()
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if len(line) == 0:
            continue

        request_id = 0
        trace_id = str(uuid4())

        try:
            request = json.loads(line)
            request_id = int(request.get("id", 0))
            method = str(request.get("method", "")).strip()
            params = request.get("params", {})
            trace_id = str(request.get("trace_id", trace_id))

            if not isinstance(params, dict):
                raise WorkerError(
                    message="params must be an object",
                    code="ERR_VALIDATION",
                    category="validation",
                    trace_id=trace_id,
                )

            result = worker.handle(method, params, trace_id)
            response = {
                "id": request_id,
                "result": result,
            }
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()
        except PolicyError as exc:
            error = WorkerError(
                message=exc.message,
                code=exc.code,
                category="validation",
                trace_id=trace_id,
            )
            response = {"id": request_id, "error": error_response(error)}
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()
        except WorkerError as exc:
            response = {"id": request_id, "error": error_response(exc)}
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()
        except RuntimeError as exc:
            error = WorkerError(
                message=str(exc),
                code="ERR_DEPENDENCY",
                category="dependency",
                trace_id=trace_id,
            )
            response = {"id": request_id, "error": error_response(error)}
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()
        except Exception as exc:  # noqa: BLE001
            traceback_text = traceback.format_exc(limit=5)
            json_log(
                "error",
                "worker-unhandled-exception",
                {
                    "trace_id": trace_id,
                    "error": str(exc),
                    "traceback": traceback_text,
                },
            )
            error = WorkerError(
                message="Unexpected worker error",
                code="ERR_INTERNAL",
                category="system",
                trace_id=trace_id,
            )
            response = {"id": request_id, "error": error_response(error)}
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
