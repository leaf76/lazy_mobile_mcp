import { mkdirSync } from "node:fs";
import path from "node:path";
import Database from "better-sqlite3";

const SLEEP_ARRAY = new Int32Array(new SharedArrayBuffer(4));

function sleepMs(durationMs: number): void {
  Atomics.wait(SLEEP_ARRAY, 0, 0, durationMs);
}

function parseJsonRecord(value: string): Record<string, unknown> {
  const parsed = JSON.parse(value);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return {};
  }
  return parsed as Record<string, unknown>;
}

export interface CreateSessionInput {
  sessionId: string;
  deviceId: string;
  appId: string;
  platform: string;
  traceId: string;
  startedAt?: string;
}

export interface InsertPerfSampleInput {
  sessionId: string;
  ts: string;
  cpuPct: number | null;
  memoryMb: number | null;
  launchMs: number | null;
  fps: number | null;
  jankPct: number | null;
  metricFlags: Record<string, string>;
}

export interface InsertArtifactInput {
  artifactId: string;
  sessionId: string | null;
  artifactType: string;
  filePath: string;
  createdAt: string;
  meta: Record<string, unknown>;
}

export interface ListSamplesInput {
  sessionId: string;
  limit: number;
  cursor: number;
}

export interface ListSessionsInput {
  limit: number;
  cursor: string | null;
}

export interface PerfSampleRow {
  id: number;
  ts: string;
  cpu_pct: number | null;
  memory_mb: number | null;
  launch_ms: number | null;
  fps: number | null;
  jank_pct: number | null;
  metric_flags: Record<string, unknown>;
}

export interface ListSamplesResult {
  samples: PerfSampleRow[];
  next_cursor: number | null;
}

export interface SessionRow {
  session_id: string;
  device_id: string;
  app_id: string;
  platform: string;
  started_at: string;
  ended_at: string | null;
  status: string;
  trace_id: string;
}

export class Storage {
  private readonly maxLockRetries = 3;
  private readonly retryBaseDelayMs = 50;

  constructor(private readonly dbPath: string) {}

  initialize(): void {
    this.withConnection((db) => {
      db.prepare(
        `
        CREATE TABLE IF NOT EXISTS devices (
            device_id TEXT PRIMARY KEY,
            platform TEXT NOT NULL,
            host TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            capabilities_json TEXT NOT NULL
        )
        `
      ).run();

      db.prepare(
        `
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            app_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            status TEXT NOT NULL,
            trace_id TEXT NOT NULL
        )
        `
      ).run();

      db.prepare(
        `
        CREATE TABLE IF NOT EXISTS perf_samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            ts TEXT NOT NULL,
            cpu_pct REAL,
            memory_mb REAL,
            launch_ms REAL,
            fps REAL,
            jank_pct REAL,
            metric_flags_json TEXT NOT NULL
        )
        `
      ).run();

      db.prepare(
        `
        CREATE TABLE IF NOT EXISTS artifacts (
            artifact_id TEXT PRIMARY KEY,
            session_id TEXT,
            type TEXT NOT NULL,
            file_path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            meta_json TEXT NOT NULL
        )
        `
      ).run();

      db.prepare(
        `
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            risk_level TEXT NOT NULL,
            device_id TEXT,
            created_at TEXT NOT NULL,
            result_code TEXT NOT NULL
        )
        `
      ).run();
    });
  }

  upsertDevice(input: {
    deviceId: string;
    platform: string;
    host: string;
    lastSeenAt: string;
    capabilities: Record<string, unknown>;
  }): void {
    const capabilitiesJson = JSON.stringify(input.capabilities);
    this.withConnection((db) => {
      db.prepare(
        `
        INSERT INTO devices(device_id, platform, host, last_seen_at, capabilities_json)
        VALUES(?, ?, ?, ?, ?)
        ON CONFLICT(device_id)
        DO UPDATE SET
            platform=excluded.platform,
            host=excluded.host,
            last_seen_at=excluded.last_seen_at,
            capabilities_json=excluded.capabilities_json
        `
      ).run(input.deviceId, input.platform, input.host, input.lastSeenAt, capabilitiesJson);
    });
  }

  createSession(input: CreateSessionInput): void {
    const startedAt = input.startedAt ?? new Date().toISOString();
    this.withConnection((db) => {
      db.prepare(
        `
        INSERT INTO sessions(session_id, device_id, app_id, platform, started_at, ended_at, status, trace_id)
        VALUES(?, ?, ?, ?, ?, NULL, ?, ?)
        `
      ).run(input.sessionId, input.deviceId, input.appId, input.platform, startedAt, "running", input.traceId);
    });
  }

  closeSession(input: { sessionId: string; endedAt: string; status: string }): void {
    this.withConnection((db) => {
      db.prepare(
        `
        UPDATE sessions
        SET ended_at = ?, status = ?
        WHERE session_id = ?
        `
      ).run(input.endedAt, input.status, input.sessionId);
    });
  }

  insertPerfSample(input: InsertPerfSampleInput): void {
    const metricFlagsJson = JSON.stringify(input.metricFlags);
    this.withConnection((db) => {
      db.prepare(
        `
        INSERT INTO perf_samples(session_id, ts, cpu_pct, memory_mb, launch_ms, fps, jank_pct, metric_flags_json)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        `
      ).run(
        input.sessionId,
        input.ts,
        input.cpuPct,
        input.memoryMb,
        input.launchMs,
        input.fps,
        input.jankPct,
        metricFlagsJson
      );
    });
  }

  insertArtifact(input: InsertArtifactInput): void {
    const metaJson = JSON.stringify(input.meta);
    this.withConnection((db) => {
      db.prepare(
        `
        INSERT INTO artifacts(artifact_id, session_id, type, file_path, created_at, meta_json)
        VALUES(?, ?, ?, ?, ?, ?)
        `
      ).run(input.artifactId, input.sessionId, input.artifactType, input.filePath, input.createdAt, metaJson);
    });
  }

  insertAuditLog(input: {
    traceId: string;
    toolName: string;
    riskLevel: string;
    deviceId: string | null;
    createdAt: string;
    resultCode: string;
  }): void {
    this.withConnection((db) => {
      db.prepare(
        `
        INSERT INTO audit_logs(trace_id, tool_name, risk_level, device_id, created_at, result_code)
        VALUES(?, ?, ?, ?, ?, ?)
        `
      ).run(input.traceId, input.toolName, input.riskLevel, input.deviceId, input.createdAt, input.resultCode);
    });
  }

  listSamples(input: ListSamplesInput): ListSamplesResult {
    return this.withConnection((db) => {
      const rows = db
        .prepare(
          `
          SELECT id, ts, cpu_pct, memory_mb, launch_ms, fps, jank_pct, metric_flags_json
          FROM perf_samples
          WHERE session_id = ? AND id > ?
          ORDER BY id ASC
          LIMIT ?
          `
        )
        .all(input.sessionId, input.cursor, input.limit) as Array<{
        id: number;
        ts: string;
        cpu_pct: number | null;
        memory_mb: number | null;
        launch_ms: number | null;
        fps: number | null;
        jank_pct: number | null;
        metric_flags_json: string;
      }>;

      const samples = rows.map((row) => ({
        id: row.id,
        ts: row.ts,
        cpu_pct: row.cpu_pct,
        memory_mb: row.memory_mb,
        launch_ms: row.launch_ms,
        fps: row.fps,
        jank_pct: row.jank_pct,
        metric_flags: parseJsonRecord(row.metric_flags_json)
      }));

      const nextCursor = rows.length > 0 ? rows[rows.length - 1]?.id ?? null : null;
      return {
        samples,
        next_cursor: nextCursor
      };
    });
  }

  listSessions(input: ListSessionsInput): SessionRow[] {
    return this.withConnection((db) => {
      if (input.cursor === null) {
        return db
          .prepare(
            `
            SELECT session_id, device_id, app_id, platform, started_at, ended_at, status, trace_id
            FROM sessions
            ORDER BY session_id ASC
            LIMIT ?
            `
          )
          .all(input.limit) as SessionRow[];
      }

      return db
        .prepare(
          `
          SELECT session_id, device_id, app_id, platform, started_at, ended_at, status, trace_id
          FROM sessions
          WHERE session_id > ?
          ORDER BY session_id ASC
          LIMIT ?
          `
        )
        .all(input.cursor, input.limit) as SessionRow[];
    });
  }

  protected connect(): Database.Database {
    mkdirSync(path.dirname(this.dbPath), { recursive: true });
    const db = new Database(this.dbPath);
    db.pragma("journal_mode = WAL");
    db.pragma("busy_timeout = 5000");
    return db;
  }

  private withConnection<T>(operation: (db: Database.Database) => T): T {
    let attempt = 0;

    while (true) {
      try {
        const db = this.connect();
        try {
          return operation(db);
        } finally {
          db.close();
        }
      } catch (error: unknown) {
        if (!this.isLockedError(error) || attempt >= this.maxLockRetries) {
          throw error;
        }

        sleepMs(this.retryBaseDelayMs * 2 ** attempt);
        attempt += 1;
      }
    }
  }

  private isLockedError(error: unknown): boolean {
    if (!(error instanceof Error)) {
      return false;
    }

    return error.message.toLowerCase().includes("locked");
  }
}
