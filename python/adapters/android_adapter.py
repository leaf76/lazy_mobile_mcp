from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AndroidDevice:
    device_id: str
    state: str


class AndroidAdapter:
    def __init__(self, adb_bin: str = "adb") -> None:
        self._adb_bin = adb_bin

    def list_devices(self) -> list[dict[str, Any]]:
        result = self._run([self._adb_bin, "devices"])
        lines = result.stdout.strip().splitlines()
        devices: list[dict[str, Any]] = []
        for line in lines[1:]:
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            device = AndroidDevice(device_id=parts[0], state=parts[1])
            devices.append(
                {
                    "device_id": device.device_id,
                    "platform": "android",
                    "state": device.state,
                    "capabilities": self.get_capabilities(),
                }
            )
        return devices

    def get_capabilities(self) -> dict[str, list[str]]:
        return {
            "actions": [
                "mobile.screenshot",
                "mobile.tap",
                "mobile.swipe",
                "mobile.input_text",
                "mobile.launch_app",
                "mobile.stop_app",
                "mobile.start_perf_session",
                "mobile.stop_perf_session",
                "mobile.get_perf_samples",
            ],
            "metrics": ["cpu_pct", "memory_mb", "launch_ms"],
            "unsupported": [],
        }

    def screenshot(self, *, device_id: str, output_path: Path) -> dict[str, Any]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as handle:
            process = subprocess.run(
                [self._adb_bin, "-s", device_id, "exec-out", "screencap", "-p"],
                stdout=handle,
                stderr=subprocess.PIPE,
                check=False,
                timeout=10,
            )
        if process.returncode != 0:
            raise RuntimeError(process.stderr.decode("utf-8", errors="ignore"))

        resolution = self._get_resolution(device_id)
        return {
            "path": str(output_path),
            "width": resolution[0],
            "height": resolution[1],
        }

    def tap(self, *, device_id: str, x: int, y: int) -> None:
        self._run([self._adb_bin, "-s", device_id, "shell", "input", "tap", str(x), str(y)])

    def swipe(self, *, device_id: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int) -> None:
        self._run(
            [
                self._adb_bin,
                "-s",
                device_id,
                "shell",
                "input",
                "swipe",
                str(x1),
                str(y1),
                str(x2),
                str(y2),
                str(duration_ms),
            ]
        )

    def input_text(self, *, device_id: str, text: str) -> None:
        escaped = text.replace(" ", "%s")
        self._run([self._adb_bin, "-s", device_id, "shell", "input", "text", escaped])

    def launch_app(self, *, device_id: str, app_id: str) -> dict[str, float]:
        start = time.monotonic()
        self._run(
            [
                self._adb_bin,
                "-s",
                device_id,
                "shell",
                "monkey",
                "-p",
                app_id,
                "-c",
                "android.intent.category.LAUNCHER",
                "1",
            ]
        )
        launch_ms = (time.monotonic() - start) * 1000
        return {"launch_ms": launch_ms}

    def stop_app(self, *, device_id: str, app_id: str) -> None:
        self._run([self._adb_bin, "-s", device_id, "shell", "am", "force-stop", app_id])

    def collect_metrics(self, *, device_id: str, app_id: str, metrics: list[str]) -> dict[str, float]:
        result: dict[str, float] = {}

        if "cpu_pct" in metrics:
            result["cpu_pct"] = self._read_cpu_pct(device_id=device_id, app_id=app_id)

        if "memory_mb" in metrics:
            result["memory_mb"] = self._read_memory_mb(device_id=device_id, app_id=app_id)

        if "launch_ms" in metrics:
            result["launch_ms"] = 0.0

        return result

    def _read_cpu_pct(self, *, device_id: str, app_id: str) -> float:
        command = [self._adb_bin, "-s", device_id, "shell", "top", "-n", "1", "-b"]
        output = self._run(command).stdout
        for line in output.splitlines():
            if app_id not in line:
                continue
            # Accept either "12%" or "12.5%" patterns.
            match = re.search(r"([0-9]+(?:\.[0-9]+)?)%", line)
            if match:
                return float(match.group(1))
        return 0.0

    def _read_memory_mb(self, *, device_id: str, app_id: str) -> float:
        output = self._run([self._adb_bin, "-s", device_id, "shell", "dumpsys", "meminfo", app_id]).stdout
        for line in output.splitlines():
            if "TOTAL PSS" not in line:
                continue
            numbers = re.findall(r"\d+", line)
            if numbers:
                pss_kb = float(numbers[0])
                return pss_kb / 1024
        return 0.0

    def _get_resolution(self, device_id: str) -> tuple[int, int]:
        output = self._run([self._adb_bin, "-s", device_id, "shell", "wm", "size"]).stdout
        match = re.search(r"(\d+)x(\d+)", output)
        if not match:
            return (0, 0)
        return (int(match.group(1)), int(match.group(2)))

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
