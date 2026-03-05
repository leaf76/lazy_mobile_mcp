import { describe, expect, it } from "vitest";
import { normalizeSample, PerfCollector } from "../src/perfCollector.js";

describe("normalizeSample", () => {
  it("marks unsupported metrics", () => {
    const sample = normalizeSample(
      {
        cpu_pct: 30.5,
        memory_mb: 128,
        launch_ms: 900
      },
      ["cpu_pct", "memory_mb", "fps"]
    );

    expect(sample.metric_flags.fps).toBe("unsupported");
  });

  it("collects an immediate sample and returns sample count on stop", () => {
    const samples: unknown[] = [];
    const storage = {
      insertPerfSample(input: unknown) {
        samples.push(input);
      }
    } as any;

    const collector = new PerfCollector(storage);
    collector.startSession({
      sessionId: "session-1",
      intervalMs: 60_000,
      metrics: ["cpu_pct"],
      sampleFn: () => ({ cpu_pct: 1 })
    });

    const sampleCount = collector.stopSession({ sessionId: "session-1" });

    expect(samples.length).toBe(1);
    expect(sampleCount).toBe(1);
  });
});
