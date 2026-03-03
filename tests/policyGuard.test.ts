import { describe, expect, it } from "vitest";
import { PolicyGuard } from "../src/policyGuard.js";

describe("PolicyGuard", () => {
  it("allows known device", () => {
    const guard = new PolicyGuard({ allowlist: ["device-a"] });
    expect(() => guard.assertDeviceAllowed("device-a")).not.toThrow();
  });

  it("rejects unknown device", () => {
    const guard = new PolicyGuard({ allowlist: ["device-a"] });
    expect(() => guard.assertDeviceAllowed("device-b")).toThrow(/ERR_DEVICE_NOT_ALLOWED/);
  });

  it("requires confirm for high risk tool", () => {
    const guard = new PolicyGuard({ allowlist: ["device-a"], highRiskTools: ["mobile.factory_reset"] });
    expect(() =>
      guard.assertToolRisk({
        toolName: "mobile.factory_reset",
        args: {}
      })
    ).toThrow(/ERR_CONFIRM_REQUIRED/);
  });

  it("accepts confirm and reason for high risk tool", () => {
    const guard = new PolicyGuard({ allowlist: ["device-a"], highRiskTools: ["mobile.factory_reset"] });
    expect(() =>
      guard.assertToolRisk({
        toolName: "mobile.factory_reset",
        args: { confirm: true, reason: "maintenance" }
      })
    ).not.toThrow();
  });
});
