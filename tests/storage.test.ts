import os from "node:os";
import path from "node:path";
import { mkdtempSync, rmSync } from "node:fs";
import { describe, expect, it, afterEach } from "vitest";
import Database from "better-sqlite3";
import { Storage } from "../src/storage.js";

const tempDirs: string[] = [];

function makeTempDbPath(): string {
  const dir = mkdtempSync(path.join(os.tmpdir(), "lazy-mobile-storage-"));
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

describe("Storage", () => {
  it("initializes schema", () => {
    const dbPath = makeTempDbPath();
    const storage = new Storage(dbPath);
    storage.initialize();

    const db = new Database(dbPath, { readonly: true });
    const row = db
      .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'")
      .get() as { name?: string } | undefined;
    db.close();

    expect(row?.name).toBe("sessions");
  });

  it("inserts and lists sessions", () => {
    const dbPath = makeTempDbPath();
    const storage = new Storage(dbPath);
    storage.initialize();

    storage.createSession({
      sessionId: "session-1",
      deviceId: "emulator-5554",
      appId: "com.demo.app",
      platform: "android",
      traceId: "trace-1"
    });

    const sessions = storage.listSessions({ limit: 10, cursor: null });
    expect(sessions[0]?.session_id).toBe("session-1");
  });

  it("stores and paginates perf samples", () => {
    const dbPath = makeTempDbPath();
    const storage = new Storage(dbPath);
    storage.initialize();

    storage.insertPerfSample({
      sessionId: "s-1",
      ts: "2026-01-01T00:00:00.000Z",
      cpuPct: 12.5,
      memoryMb: 128,
      launchMs: 0,
      fps: null,
      jankPct: null,
      metricFlags: { cpu_pct: "ok" }
    });

    storage.insertPerfSample({
      sessionId: "s-1",
      ts: "2026-01-01T00:00:01.000Z",
      cpuPct: 13,
      memoryMb: 129,
      launchMs: 0,
      fps: null,
      jankPct: null,
      metricFlags: { cpu_pct: "ok" }
    });

    const first = storage.listSamples({ sessionId: "s-1", limit: 1, cursor: 0 });
    expect(first.samples).toHaveLength(1);
    expect(first.next_cursor).toBe(first.samples[0]?.id);

    const second = storage.listSamples({
      sessionId: "s-1",
      limit: 10,
      cursor: first.next_cursor ?? 0
    });
    expect(second.samples).toHaveLength(1);
  });
});
