from policy_guard import PolicyGuard, PolicyError


def test_policy_guard_allows_known_device() -> None:
    guard = PolicyGuard(allowlist={"device-a"}, high_risk_tools={"mobile.factory_reset"})
    guard.assert_device_allowed("device-a")


def test_policy_guard_rejects_unknown_device() -> None:
    guard = PolicyGuard(allowlist={"device-a"}, high_risk_tools={"mobile.factory_reset"})
    try:
        guard.assert_device_allowed("device-b")
        assert False, "Expected PolicyError"
    except PolicyError as exc:
        assert exc.code == "ERR_DEVICE_NOT_ALLOWED"


def test_policy_guard_requires_confirm() -> None:
    guard = PolicyGuard(allowlist={"device-a"}, high_risk_tools={"mobile.factory_reset"})
    try:
        guard.assert_tool_risk("mobile.factory_reset", {})
        assert False, "Expected PolicyError"
    except PolicyError as exc:
        assert exc.code == "ERR_CONFIRM_REQUIRED"
