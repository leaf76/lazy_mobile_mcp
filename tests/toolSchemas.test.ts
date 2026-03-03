import { describe, expect, it } from "vitest";
import { toolValidators } from "../src/toolSchemas.js";

describe("toolSchemas", () => {
  it("validates tap args", () => {
    const parsed = toolValidators["mobile.tap"].parse({ x: 10, y: 20 });
    expect(parsed.x).toBe(10);
    expect(parsed.y).toBe(20);
  });

  it("fails for invalid swipe args", () => {
    expect(() =>
      toolValidators["mobile.swipe"].parse({ x1: 1, y1: 2, x2: 3, y2: 4, duration_ms: 0 })
    ).toThrow();
  });

  it("enforces perf interval boundaries", () => {
    expect(() =>
      toolValidators["mobile.start_perf_session"].parse({ app_id: "com.example.app", interval_ms: 100 })
    ).toThrow();
  });
});
