from __future__ import annotations

from pathlib import Path
import subprocess

from adapters.ios_adapter import IOSAdapter


class FakeIOSAdapter(IOSAdapter):
    def __init__(self) -> None:
        super().__init__(wda_base_url=None)
        self.commands: list[list[str]] = []
        self.devicectl_calls: list[list[str]] = []
        self.devicectl_results: list[dict] = []
        self.simulator_boot_state: dict[str, str] = {"SIM-1234-AAAA": "Shutdown"}

    @property
    def is_supported_host(self) -> bool:  # type: ignore[override]
        return True

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:  # type: ignore[override]
        self.commands.append(command)
        if command[:4] == ["xcrun", "xctrace", "list", "devices"]:
            stdout = "iPhone 16 Simulator (18.0) (SIM-1234-AAAA)\nJohn iPhone (17.2) (PHY-7777-BBBB)"
            return subprocess.CompletedProcess(args=command, returncode=0, stdout=stdout, stderr="")
        if command[:4] == ["xcrun", "simctl", "list", "devices"]:
            device_id = command[4]
            state = self.simulator_boot_state.get(device_id, "Shutdown")
            stdout = f"iPhone 16 Simulator ({device_id}) ({state})"
            return subprocess.CompletedProcess(args=command, returncode=0, stdout=stdout, stderr="")
        if command[:3] == ["xcrun", "simctl", "boot"]:
            device_id = command[3]
            self.simulator_boot_state[device_id] = "Booted"
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")
        if command[:3] == ["xcrun", "simctl", "bootstatus"]:
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")
        return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

    def _run_devicectl_json(self, subcommand_args: list[str]) -> dict:  # type: ignore[override]
        self.devicectl_calls.append(subcommand_args)
        if len(self.devicectl_results) == 0:
            return {}
        return self.devicectl_results.pop(0)

    def _discover_wda_base_url(self) -> str | None:  # type: ignore[override]
        return None


def test_list_devices_detects_target_type() -> None:
    adapter = FakeIOSAdapter()

    devices = adapter.list_devices()

    assert len(devices) == 2
    simulator = next(device for device in devices if device["target_type"] == "simulator")
    physical = next(device for device in devices if device["target_type"] == "physical")
    assert "mobile.screenshot" in simulator["capabilities"]["actions"]
    assert "mobile.screenshot" in physical["capabilities"]["unsupported"]


def test_launch_app_uses_simctl_for_simulator() -> None:
    adapter = FakeIOSAdapter()
    adapter.list_devices()

    adapter.launch_app(device_id="SIM-1234-AAAA", app_id="com.example.app")

    assert ["xcrun", "simctl", "launch", "SIM-1234-AAAA", "com.example.app"] in adapter.commands


def test_launch_app_uses_devicectl_for_physical() -> None:
    adapter = FakeIOSAdapter()
    adapter.list_devices()

    adapter.launch_app(device_id="PHY-7777-BBBB", app_id="com.example.app")

    assert any(call[:3] == ["device", "process", "launch"] for call in adapter.devicectl_calls)


def test_stop_app_uses_pid_terminate_for_physical() -> None:
    adapter = FakeIOSAdapter()
    adapter.list_devices()
    adapter.devicectl_results = [
        {
            "result": {
                "processes": [
                    {
                        "bundleIdentifier": "com.example.app",
                        "pid": 1234,
                    }
                ]
            }
        },
        {},
    ]

    adapter.stop_app(device_id="PHY-7777-BBBB", app_id="com.example.app")

    assert adapter.devicectl_calls[0][:3] == ["device", "info", "processes"]
    assert adapter.devicectl_calls[1][:3] == ["device", "process", "terminate"]
    assert "1234" in adapter.devicectl_calls[1]


def test_parse_xctrace_line_with_optional_tail_simulator_tag() -> None:
    parsed_without_tail = IOSAdapter._parse_xctrace_device_line("iPhone 16 Simulator (18.0) (SIM-1234-AAAA)")
    parsed_with_tail = IOSAdapter._parse_xctrace_device_line("iPhone 15 (17.2) (SIM-9999-ZZZZ) (Simulator)")

    assert parsed_without_tail == ("SIM-1234-AAAA", "iPhone 16 Simulator", "simulator")
    assert parsed_with_tail == ("SIM-9999-ZZZZ", "iPhone 15", "simulator")


def test_screenshot_boots_simulator_before_capture(tmp_path: Path) -> None:
    adapter = FakeIOSAdapter()
    adapter.list_devices()
    output_path = tmp_path / "sim.png"

    adapter.screenshot(device_id="SIM-1234-AAAA", output_path=output_path)

    assert ["xcrun", "simctl", "boot", "SIM-1234-AAAA"] in adapter.commands
    assert ["xcrun", "simctl", "bootstatus", "SIM-1234-AAAA", "-b"] in adapter.commands
    assert ["xcrun", "simctl", "io", "SIM-1234-AAAA", "screenshot", str(output_path)] in adapter.commands


class FakeWDAIOSAdapter(FakeIOSAdapter):
    def __init__(self) -> None:
        super().__init__()
        self._wda_base_url = "http://127.0.0.1:8100"
        self.wda_calls: list[tuple[str, str, dict | None]] = []
        self.wda_session_id = "session-1"
        self.fail_first_tap_for_invalid_session = False

    def _wda_json_call(self, method: str, path: str, payload: dict | None) -> dict:  # type: ignore[override]
        self.wda_calls.append((method, path, payload))

        if path == "/session":
            return {"value": {"sessionId": self.wda_session_id}}

        if self.fail_first_tap_for_invalid_session and path.endswith("/wda/tap"):
            self.fail_first_tap_for_invalid_session = False
            raise RuntimeError("invalid session id")

        if path.endswith("/screenshot"):
            # base64("fake-png-data")
            return {"value": "ZmFrZS1wbmctZGF0YQ=="}

        return {"value": {}}


class FakeAutoDiscoverWDAIOSAdapter(FakeWDAIOSAdapter):
    def __init__(self) -> None:
        super().__init__()
        self._wda_base_url = None
        self.discovery_count = 0

    def _discover_wda_base_url(self) -> str | None:  # type: ignore[override]
        self.discovery_count += 1
        return "http://127.0.0.1:8100"


class FakeNoDiscoverWDAIOSAdapter(FakeWDAIOSAdapter):
    def __init__(self) -> None:
        super().__init__()
        self._wda_base_url = None

    def _discover_wda_base_url(self) -> str | None:  # type: ignore[override]
        return None


def test_physical_screenshot_uses_wda(tmp_path: Path) -> None:
    adapter = FakeWDAIOSAdapter()
    adapter.list_devices()
    output_path = tmp_path / "physical.png"

    result = adapter.screenshot(device_id="PHY-7777-BBBB", output_path=output_path)

    assert result["path"] == str(output_path)
    assert output_path.read_bytes() == b"fake-png-data"
    assert any(call[1].endswith("/screenshot") for call in adapter.wda_calls)


def test_ios_actions_create_and_reuse_wda_session() -> None:
    adapter = FakeWDAIOSAdapter()
    adapter.list_devices()

    adapter.tap(device_id="PHY-7777-BBBB", x=10, y=20)
    adapter.swipe(device_id="PHY-7777-BBBB", x1=10, y1=20, x2=30, y2=40, duration_ms=500)
    adapter.input_text(device_id="PHY-7777-BBBB", text="hello")

    session_creates = [call for call in adapter.wda_calls if call[1] == "/session"]
    assert len(session_creates) == 1
    assert any(call[1] == "/session/session-1/wda/tap" for call in adapter.wda_calls)
    assert any(call[1] == "/session/session-1/wda/dragfromtoforduration" for call in adapter.wda_calls)
    assert any(call[1] == "/session/session-1/wda/keys" for call in adapter.wda_calls)


def test_ios_actions_recreate_wda_session_after_invalid_session() -> None:
    adapter = FakeWDAIOSAdapter()
    adapter.list_devices()
    adapter.fail_first_tap_for_invalid_session = True

    adapter.tap(device_id="PHY-7777-BBBB", x=1, y=2)

    session_creates = [call for call in adapter.wda_calls if call[1] == "/session"]
    assert len(session_creates) == 2


def test_ios_actions_auto_discover_wda_base_url_once() -> None:
    adapter = FakeAutoDiscoverWDAIOSAdapter()
    adapter.list_devices()

    adapter.tap(device_id="PHY-7777-BBBB", x=1, y=2)
    adapter.swipe(device_id="PHY-7777-BBBB", x1=1, y1=2, x2=3, y2=4, duration_ms=300)

    assert adapter.discovery_count == 1
    assert adapter._wda_base_url == "http://127.0.0.1:8100"


def test_get_capabilities_uses_wda_auto_discovery_for_physical() -> None:
    adapter = FakeAutoDiscoverWDAIOSAdapter()
    adapter.list_devices()

    capabilities = adapter.get_capabilities(device_id="PHY-7777-BBBB")

    assert "mobile.screenshot" in capabilities["actions"]
    assert "mobile.tap" in capabilities["actions"]
    assert "mobile.swipe" in capabilities["actions"]
    assert "mobile.input_text" in capabilities["actions"]
    assert adapter.discovery_count == 1


def test_ios_actions_fail_when_wda_auto_discovery_fails() -> None:
    adapter = FakeNoDiscoverWDAIOSAdapter()
    adapter.list_devices()

    try:
        adapter.tap(device_id="PHY-7777-BBBB", x=1, y=2)
        assert False, "Expected RuntimeError"
    except RuntimeError as exc:
        assert "auto-discovery failed" in str(exc)
