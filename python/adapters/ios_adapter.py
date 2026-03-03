from __future__ import annotations

import base64
import json
import platform
import re
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class IOSAdapter:
    def __init__(self, wda_base_url: str | None = None) -> None:
        self._wda_base_url = wda_base_url
        self._device_kinds: dict[str, str] = {}
        self._wda_sessions: dict[str, str] = {}
        self._wda_session_lock = threading.Lock()
        self._wda_discovery_ports = (8100, 8101, 8200, 8201)

    @property
    def is_supported_host(self) -> bool:
        return platform.system().lower() == "darwin"

    def list_devices(self) -> list[dict[str, Any]]:
        if not self.is_supported_host:
            return []

        output = self._run(["xcrun", "xctrace", "list", "devices"]).stdout
        devices: list[dict[str, Any]] = []

        for line in output.splitlines():
            parsed = self._parse_xctrace_device_line(line)
            if parsed is None:
                continue

            device_id, name, target_type = parsed
            self._device_kinds[device_id] = target_type
            devices.append(
                {
                    "device_id": device_id,
                    "platform": "ios",
                    "state": "available",
                    "name": name,
                    "target_type": target_type,
                    "capabilities": self.get_capabilities(device_id=device_id),
                }
            )

        return devices

    def get_capabilities(self, *, device_id: str | None = None) -> dict[str, list[str]]:
        target_type = self._device_kinds.get(device_id or "", "unknown")
        wda_available = self._has_wda_endpoint()

        actions = ["mobile.launch_app", "mobile.stop_app"]
        unsupported: list[str] = ["fps", "jank_pct"]

        if target_type in {"simulator", "unknown"} or (target_type == "physical" and wda_available):
            actions.append("mobile.screenshot")
        else:
            unsupported.append("mobile.screenshot")

        if wda_available:
            actions.extend(["mobile.tap", "mobile.swipe", "mobile.input_text"])
        else:
            unsupported.extend(["mobile.tap", "mobile.swipe", "mobile.input_text"])

        return {
            "actions": sorted(set(actions)),
            "metrics": ["cpu_pct", "memory_mb", "launch_ms"],
            "unsupported": sorted(set(unsupported)),
        }

    def screenshot(self, *, device_id: str, output_path: Path) -> dict[str, Any]:
        if not self.is_supported_host:
            raise RuntimeError("iOS tools require macOS host")

        target_type = self._device_type_for(device_id)
        if target_type == "physical":
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(self._wda_screenshot_png())
            return {
                "path": str(output_path),
                "width": 0,
                "height": 0,
            }

        self._ensure_simulator_booted(device_id)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._run(["xcrun", "simctl", "io", device_id, "screenshot", str(output_path)])
        return {
            "path": str(output_path),
            "width": 0,
            "height": 0,
        }

    def tap(self, *, device_id: str, x: int, y: int) -> None:
        self._wda_call_with_session(
            device_id=device_id,
            method="POST",
            session_path="/wda/tap",
            payload={"x": x, "y": y},
        )

    def swipe(self, *, device_id: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        self._wda_call_with_session(
            device_id=device_id,
            method="POST",
            session_path="/wda/dragfromtoforduration",
            payload={
                "fromX": x1,
                "fromY": y1,
                "toX": x2,
                "toY": y2,
                "duration": max(duration_ms / 1000, 0.01),
            },
        )

    def input_text(self, *, device_id: str, text: str) -> None:
        self._wda_call_with_session(
            device_id=device_id,
            method="POST",
            session_path="/wda/keys",
            payload={"value": list(text)},
        )

    def launch_app(self, *, device_id: str, app_id: str) -> dict[str, float]:
        if not self.is_supported_host:
            raise RuntimeError("iOS tools require macOS host")

        start = time.monotonic()
        target_type = self._device_type_for(device_id)

        if target_type == "simulator":
            self._ensure_simulator_booted(device_id)
            self._run(["xcrun", "simctl", "launch", device_id, app_id])
        else:
            self._run_devicectl_json(
                [
                    "device",
                    "process",
                    "launch",
                    "--device",
                    device_id,
                    "--terminate-existing",
                    "--activate",
                    app_id,
                ]
            )

        launch_ms = (time.monotonic() - start) * 1000
        return {"launch_ms": launch_ms}

    def stop_app(self, *, device_id: str, app_id: str) -> None:
        if not self.is_supported_host:
            raise RuntimeError("iOS tools require macOS host")

        target_type = self._device_type_for(device_id)

        if target_type == "simulator":
            self._run(["xcrun", "simctl", "terminate", device_id, app_id])
            return

        processes_payload = self._run_devicectl_json(
            [
                "device",
                "info",
                "processes",
                "--device",
                device_id,
            ]
        )
        pid = self._find_pid_from_processes_payload(processes_payload, app_id)
        if pid is None:
            return

        self._run_devicectl_json(
            [
                "device",
                "process",
                "terminate",
                "--device",
                device_id,
                "--pid",
                str(pid),
            ]
        )

    def collect_metrics(self, *, device_id: str, app_id: str, metrics: list[str]) -> dict[str, float]:
        del device_id
        del app_id
        result: dict[str, float] = {}
        for metric in metrics:
            if metric in {"cpu_pct", "memory_mb", "launch_ms"}:
                result[metric] = 0.0
        return result

    def _ensure_simulator_booted(self, device_id: str) -> None:
        if self._is_simulator_booted(device_id):
            return

        self._run(["xcrun", "simctl", "boot", device_id])
        self._run(["xcrun", "simctl", "bootstatus", device_id, "-b"])

    def _is_simulator_booted(self, device_id: str) -> bool:
        output = self._run(["xcrun", "simctl", "list", "devices", device_id]).stdout
        for line in output.splitlines():
            if device_id in line and "(Booted)" in line:
                return True
        return False

    def _wda_call(self, method: str, path: str, payload: dict[str, Any]) -> None:
        self._wda_json_call(method, path, payload)

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(
                json.dumps(
                    {
                        "command": command,
                        "code": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    }
                )
            )
        return result

    def _run_devicectl_json(self, subcommand_args: list[str]) -> dict[str, Any]:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
            json_path = Path(handle.name)

        command = ["xcrun", "devicectl", "--quiet", "--json-output", str(json_path), *subcommand_args]
        self._run(command)

        try:
            text = json_path.read_text(encoding="utf-8")
            return json.loads(text)
        finally:
            json_path.unlink(missing_ok=True)

    def _device_type_for(self, device_id: str) -> str:
        if device_id in self._device_kinds:
            return self._device_kinds[device_id]

        for device in self.list_devices():
            if device.get("device_id") == device_id:
                return str(device.get("target_type", "unknown"))

        return "unknown"

    @staticmethod
    def _parse_xctrace_device_line(line: str) -> tuple[str, str, str] | None:
        stripped = line.strip()
        if len(stripped) == 0 or stripped.startswith("=="):
            return None
        groups = re.findall(r"\(([^()]*)\)", stripped)
        if len(groups) < 2:
            return None

        line_lower = stripped.lower()
        tail_group = groups[-1].strip().lower()
        if tail_group == "simulator":
            target_type = "simulator"
            device_id = groups[-2].strip()
        elif "simulator" in line_lower:
            target_type = "simulator"
            device_id = groups[-1].strip()
        else:
            target_type = "physical"
            device_id = groups[-1].strip()
        if len(device_id) < 6:
            return None

        name_part = stripped.split("(")[0].strip()
        return device_id, name_part, target_type

    @classmethod
    def _find_pid_from_processes_payload(cls, payload: dict[str, Any], app_id: str) -> int | None:
        pid_keys = {"pid", "processidentifier", "process_id", "processid"}
        identifier_keys = {"bundleidentifier", "bundle_id", "bundleid", "identifier", "name", "processname"}

        def walk(node: Any) -> int | None:
            if isinstance(node, dict):
                lowered = {str(key).lower(): value for key, value in node.items()}
                identifier_match = False
                for key in identifier_keys:
                    value = lowered.get(key)
                    if isinstance(value, str) and (value == app_id or value.endswith(f".{app_id.split('.')[-1]}")):
                        identifier_match = True
                        break

                if identifier_match:
                    for key in pid_keys:
                        value = lowered.get(key)
                        if isinstance(value, int):
                            return value
                        if isinstance(value, str) and value.isdigit():
                            return int(value)

                for child in node.values():
                    found = walk(child)
                    if found is not None:
                        return found

            if isinstance(node, list):
                for item in node:
                    found = walk(item)
                    if found is not None:
                        return found

            return None

        return walk(payload)

    def _wda_call_with_session(self, *, device_id: str, method: str, session_path: str, payload: dict[str, Any]) -> None:
        session_id = self._ensure_wda_session(device_id)
        full_path = f"/session/{session_id}{session_path}"

        try:
            self._wda_json_call(method, full_path, payload)
        except RuntimeError as exc:
            if not self._is_invalid_session_error(exc):
                raise

            self._invalidate_wda_session(device_id, expected_session_id=session_id)
            retry_session_id = self._ensure_wda_session(device_id)
            retry_path = f"/session/{retry_session_id}{session_path}"
            self._wda_json_call(method, retry_path, payload)

    def _ensure_wda_session(self, device_id: str) -> str:
        self._get_wda_base_url()

        with self._wda_session_lock:
            existing = self._wda_sessions.get(device_id)
        if existing is not None:
            return existing

        target_type = self._device_type_for(device_id)
        if target_type == "simulator":
            self._ensure_simulator_booted(device_id)

        payload_candidates: list[dict[str, Any] | None] = [
            {
                "capabilities": {
                    "alwaysMatch": {"udid": device_id},
                    "firstMatch": [{}],
                }
            },
            {"desiredCapabilities": {"udid": device_id}},
            None,
        ]

        errors: list[str] = []
        for payload in payload_candidates:
            try:
                response = self._wda_json_call("POST", "/session", payload)
            except RuntimeError as exc:
                errors.append(str(exc))
                continue

            session_id = self._extract_session_id(response)
            if session_id is None:
                errors.append("missing session id")
                continue

            with self._wda_session_lock:
                self._wda_sessions[device_id] = session_id
            return session_id

        raise RuntimeError(f"Unable to create WDA session for device {device_id}: {' | '.join(errors)}")

    def _invalidate_wda_session(self, device_id: str, *, expected_session_id: str | None = None) -> None:
        with self._wda_session_lock:
            existing = self._wda_sessions.get(device_id)
            if existing is None:
                return
            if expected_session_id is not None and existing != expected_session_id:
                return
            self._wda_sessions.pop(device_id, None)

    @staticmethod
    def _extract_session_id(response: dict[str, Any]) -> str | None:
        session_id = response.get("sessionId")
        if isinstance(session_id, str) and len(session_id) > 0:
            return session_id

        value = response.get("value")
        if isinstance(value, dict):
            nested = value.get("sessionId")
            if isinstance(nested, str) and len(nested) > 0:
                return nested

        return None

    @staticmethod
    def _is_invalid_session_error(exc: RuntimeError) -> bool:
        message = str(exc).lower()
        patterns = [
            "invalid session id",
            "no such session",
            "session does not exist",
            "stale session",
        ]
        return any(pattern in message for pattern in patterns)

    def _wda_screenshot_png(self) -> bytes:
        payload = self._wda_json_call("GET", "/screenshot", None)
        if not isinstance(payload, dict):
            raise RuntimeError("WDA screenshot response is invalid")

        value = payload.get("value")
        if not isinstance(value, str) or len(value) == 0:
            raise RuntimeError("WDA screenshot payload is missing image data")

        encoded = value
        if "," in encoded and encoded.lower().startswith("data:image"):
            encoded = encoded.split(",", 1)[1]

        try:
            return base64.b64decode(encoded, validate=True)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("WDA screenshot payload is not valid base64") from exc

    def _wda_json_call(self, method: str, path: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        base_url = self._get_wda_base_url()

        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url=f"{base_url.rstrip('/')}{path}",
            method=method,
            data=body,
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                status_code = response.getcode()
                if status_code >= 300:
                    raise RuntimeError(f"WDA request failed with status {status_code}")
                raw = response.read()
        except urllib.error.URLError as exc:
            raise RuntimeError(f"WDA request failed: {exc.reason}") from exc

        if len(raw) == 0:
            return {}

        try:
            parsed = json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("WDA response is not valid JSON") from exc

        if isinstance(parsed, dict):
            return parsed

        raise RuntimeError("WDA response is not a JSON object")

    def _get_wda_base_url(self) -> str:
        if self._wda_base_url:
            return self._wda_base_url

        discovered = self._discover_wda_base_url()
        if discovered is None:
            raise RuntimeError(
                "WDA base URL is not configured and auto-discovery failed. "
                "Provide WDA_BASE_URL or ensure WDA is reachable on localhost."
            )

        self._wda_base_url = discovered
        return discovered

    def _discover_wda_base_url(self) -> str | None:
        for candidate in self._candidate_wda_base_urls():
            if self._probe_wda_base_url(candidate):
                return candidate
        return None

    def _has_wda_endpoint(self) -> bool:
        if self._wda_base_url:
            return True

        discovered = self._discover_wda_base_url()
        if discovered is None:
            return False

        self._wda_base_url = discovered
        return True

    def _candidate_wda_base_urls(self) -> list[str]:
        ports = set(self._wda_discovery_ports)
        ports.update(self._list_local_listening_ports())

        # Focus on common local WDA tunnel ranges.
        sorted_ports = sorted(port for port in ports if 8000 <= port <= 9000)

        candidates: list[str] = []
        for port in sorted_ports:
            candidates.append(f"http://127.0.0.1:{port}")
            candidates.append(f"http://localhost:{port}")
        return candidates

    @staticmethod
    def _list_local_listening_ports() -> set[int]:
        command = ["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )
        except Exception:  # noqa: BLE001
            return set()

        if result.returncode != 0:
            return set()

        ports: set[int] = set()
        for line in result.stdout.splitlines():
            match = re.search(r":(\d+)\s+\(LISTEN\)", line)
            if not match:
                continue
            try:
                ports.add(int(match.group(1)))
            except ValueError:
                continue
        return ports

    def _probe_wda_base_url(self, base_url: str) -> bool:
        request = urllib.request.Request(
            url=f"{base_url.rstrip('/')}/status",
            method="GET",
        )

        try:
            with urllib.request.urlopen(request, timeout=1.5) as response:
                if response.getcode() >= 300:
                    return False
                raw = response.read()
        except Exception:  # noqa: BLE001
            return False

        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:  # noqa: BLE001
            return False

        if not isinstance(payload, dict):
            return False

        value = payload.get("value")
        if isinstance(value, dict):
            if isinstance(value.get("ready"), bool):
                return True
            message = value.get("message")
            if isinstance(message, str) and "webdriveragent" in message.lower():
                return True

        status = payload.get("status")
        if status == 0 and "value" in payload:
            return True

        return False
