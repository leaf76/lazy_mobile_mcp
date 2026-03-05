import { Storage } from "./storage.js";

export type SampleFn = (metrics: string[]) => Record<string, number>;

const SUPPORTED_METRICS = new Set(["cpu_pct", "memory_mb", "launch_ms", "fps", "jank_pct"]);

export interface NormalizedSample {
  cpu_pct: number | null;
  memory_mb: number | null;
  launch_ms: number | null;
  fps: number | null;
  jank_pct: number | null;
  metric_flags: Record<string, string>;
}

export function normalizeSample(rawSample: Record<string, number>, requestedMetrics: string[]): NormalizedSample {
  const normalized: NormalizedSample = {
    cpu_pct: rawSample.cpu_pct ?? null,
    memory_mb: rawSample.memory_mb ?? null,
    launch_ms: rawSample.launch_ms ?? null,
    fps: rawSample.fps ?? null,
    jank_pct: rawSample.jank_pct ?? null,
    metric_flags: {}
  };

  for (const metric of requestedMetrics) {
    if (!SUPPORTED_METRICS.has(metric)) {
      normalized.metric_flags[metric] = "unsupported";
      continue;
    }

    const value = normalized[metric as keyof Omit<NormalizedSample, "metric_flags">];
    normalized.metric_flags[metric] = value === null ? "unsupported" : "ok";
  }

  return normalized;
}

interface PerfSessionState {
  intervalId: NodeJS.Timeout | null;
  sampleCount: number;
}

export class PerfCollector {
  private readonly sessions = new Map<string, PerfSessionState>();

  constructor(
    private readonly storage: Storage,
    private readonly onError: (sessionId: string, error: Error) => void = () => undefined
  ) {}

  startSession(input: {
    sessionId: string;
    intervalMs: number;
    metrics: string[];
    sampleFn: SampleFn;
  }): void {
    const state: PerfSessionState = { intervalId: null, sampleCount: 0 };
    this.sessions.set(input.sessionId, state);

    const tick = (): void => {
      try {
        const rawSample = input.sampleFn(input.metrics);
        const normalized = normalizeSample(rawSample, input.metrics);

        this.storage.insertPerfSample({
          sessionId: input.sessionId,
          ts: new Date().toISOString(),
          cpuPct: normalized.cpu_pct,
          memoryMb: normalized.memory_mb,
          launchMs: normalized.launch_ms,
          fps: normalized.fps,
          jankPct: normalized.jank_pct,
          metricFlags: normalized.metric_flags
        });

        const state = this.sessions.get(input.sessionId);
        if (state) {
          state.sampleCount += 1;
        }
      } catch (error: unknown) {
        if (error instanceof Error) {
          this.onError(input.sessionId, error);
          return;
        }

        this.onError(input.sessionId, new Error("Unknown perf collector error"));
      }
    };

    tick();
    state.intervalId = setInterval(tick, input.intervalMs);
  }

  stopSession(input: { sessionId: string }): number {
    const state = this.sessions.get(input.sessionId);
    if (!state) {
      return 0;
    }

    if (state.intervalId) {
      clearInterval(state.intervalId);
    }
    this.sessions.delete(input.sessionId);
    return state.sampleCount;
  }
}
