import os from "node:os";
import path from "node:path";
import { mkdtempSync, rmSync } from "node:fs";
import { afterEach, describe, expect, it } from "vitest";
import { Worker } from "../src/worker.js";
import { AppError } from "../src/errors.js";

const tempDirs: string[] = [];

function makeTempDbPath(): string {
  const dir = mkdtempSync(path.join(os.tmpdir(), "lazy-mobile-worker-"));
  tempDirs.push(dir);
  return path.join(dir, "mobile.db");
}

afterEach(() => {
  while (tempDirs.length > 0) {
    const dir = tempDirs.pop();
    if (!dir) {
      continue;
    }
    rmSync(dir, { recursive: true, force: true });
  }
});

describe("Worker trace id", () => {
  it("uses request trace id for no active device errors", () => {
    const worker = new Worker({ sqlitePath: makeTempDbPath() });
    const traceId = "trace-request-001";

    try {
      worker.handle("mobile.screenshot", {}, traceId);
      throw new Error("expected error");
    } catch (error: unknown) {
      expect(error).toBeInstanceOf(AppError);
      const appError = error as AppError;
      expect(appError.code).toBe("ERR_NO_ACTIVE_DEVICE");
      expect(appError.traceId).toBe(traceId);
    }
  });

  it("uses request trace id for validation errors", () => {
    const worker = new Worker({ sqlitePath: makeTempDbPath() });
    (worker as any).selected = {
      deviceId: "emulator-5554",
      platform: "android"
    };
    const traceId = "trace-request-002";

    try {
      worker.handle("mobile.launch_app", {}, traceId);
      throw new Error("expected error");
    } catch (error: unknown) {
      expect(error).toBeInstanceOf(AppError);
      const appError = error as AppError;
      expect(appError.code).toBe("ERR_VALIDATION");
      expect(appError.traceId).toBe(traceId);
    }
  });
});
