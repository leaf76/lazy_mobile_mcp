import { AppError } from "./errors.js";

export interface PolicyGuardOptions {
  allowlist: string[];
  highRiskTools?: string[];
}

export interface ToolRiskInput {
  toolName: string;
  args: Record<string, unknown>;
}

export class PolicyGuard {
  private readonly allowlist: Set<string>;
  private readonly highRiskTools: Set<string>;

  constructor(options: PolicyGuardOptions) {
    this.allowlist = new Set(options.allowlist);
    this.highRiskTools = new Set(options.highRiskTools ?? []);
  }

  assertDeviceAllowed(deviceId: string): void {
    if (this.allowlist.size === 0) {
      return;
    }

    if (!this.allowlist.has(deviceId)) {
      throw new AppError({
        message: `ERR_DEVICE_NOT_ALLOWED: Device is not allowed: ${deviceId}`,
        code: "ERR_DEVICE_NOT_ALLOWED",
        category: "business",
        traceId: "policy-check"
      });
    }
  }

  assertToolRisk(input: ToolRiskInput): void {
    if (!this.highRiskTools.has(input.toolName)) {
      return;
    }

    const confirm = input.args.confirm;
    const reason = input.args.reason;
    const hasReason = typeof reason === "string" && reason.trim().length > 0;

    if (confirm !== true || !hasReason) {
      throw new AppError({
        message: "ERR_CONFIRM_REQUIRED: High-risk tool requires confirm=true and non-empty reason",
        code: "ERR_CONFIRM_REQUIRED",
        category: "validation",
        traceId: "policy-check"
      });
    }
  }
}
