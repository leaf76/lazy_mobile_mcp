from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PolicyError(Exception):
    message: str
    code: str


class PolicyGuard:
    def __init__(self, allowlist: set[str], high_risk_tools: set[str]) -> None:
        self._allowlist = allowlist
        self._high_risk_tools = high_risk_tools

    def assert_device_allowed(self, device_id: str) -> None:
        if len(self._allowlist) == 0:
            return

        if device_id not in self._allowlist:
            raise PolicyError(message=f"Device is not allowed: {device_id}", code="ERR_DEVICE_NOT_ALLOWED")

    def assert_tool_risk(self, tool_name: str, args: dict[str, object]) -> None:
        if tool_name not in self._high_risk_tools:
            return

        confirm = args.get("confirm")
        reason = args.get("reason")
        if confirm is not True or not isinstance(reason, str) or len(reason.strip()) == 0:
            raise PolicyError(
                message="High-risk tool requires confirm=true and non-empty reason",
                code="ERR_CONFIRM_REQUIRED",
            )
