import { z } from "zod";

const platformEnum = z.enum(["android", "ios", "all"]);
const metricEnum = z.enum(["cpu_pct", "memory_mb", "launch_ms", "fps", "jank_pct"]);

export const toolValidators = {
  "mobile.list_devices": z.object({
    platform: platformEnum.optional().default("all")
  }),
  "mobile.select_device": z.object({
    device_id: z.string().min(1)
  }),
  "mobile.get_capabilities": z.object({
    device_id: z.string().min(1).optional()
  }),
  "mobile.screenshot": z.object({
    device_id: z.string().min(1).optional(),
    format: z.enum(["png"]).optional().default("png"),
    save: z.boolean().optional().default(true)
  }),
  "mobile.tap": z.object({
    device_id: z.string().min(1).optional(),
    x: z.number().int().nonnegative(),
    y: z.number().int().nonnegative()
  }),
  "mobile.swipe": z.object({
    device_id: z.string().min(1).optional(),
    x1: z.number().int().nonnegative(),
    y1: z.number().int().nonnegative(),
    x2: z.number().int().nonnegative(),
    y2: z.number().int().nonnegative(),
    duration_ms: z.number().int().min(50).max(10000).optional().default(300)
  }),
  "mobile.input_text": z.object({
    device_id: z.string().min(1).optional(),
    text: z.string().min(1)
  }),
  "mobile.launch_app": z.object({
    device_id: z.string().min(1).optional(),
    app_id: z.string().min(1),
    cold_start: z.boolean().optional().default(false)
  }),
  "mobile.stop_app": z.object({
    device_id: z.string().min(1).optional(),
    app_id: z.string().min(1)
  }),
  "mobile.start_perf_session": z.object({
    device_id: z.string().min(1).optional(),
    app_id: z.string().min(1),
    interval_ms: z.number().int().min(500).max(60000).optional().default(1000),
    metrics: z.array(metricEnum).min(1).optional().default(["cpu_pct", "memory_mb", "launch_ms"])
  }),
  "mobile.stop_perf_session": z.object({
    session_id: z.string().min(1)
  }),
  "mobile.get_perf_samples": z.object({
    session_id: z.string().min(1),
    limit: z.number().int().min(1).max(500).optional().default(100),
    cursor: z.number().int().nonnegative().optional().default(0)
  })
} as const;

export type ToolName = keyof typeof toolValidators;

export type ToolArgs<TName extends ToolName> = z.infer<(typeof toolValidators)[TName]>;

export const toolDescriptions: Record<ToolName, string> = {
  "mobile.list_devices": "List available mobile devices across Android and iOS.",
  "mobile.select_device": "Select one active mobile device for subsequent tool calls.",
  "mobile.get_capabilities": "Get platform-aware supported actions and telemetry metrics.",
  "mobile.screenshot": "Capture and persist a screenshot from the selected or provided device.",
  "mobile.tap": "Tap on the device screen at pixel coordinates.",
  "mobile.swipe": "Swipe from one pixel coordinate to another.",
  "mobile.input_text": "Input text into the currently focused field.",
  "mobile.launch_app": "Launch an app and optionally measure cold start latency.",
  "mobile.stop_app": "Stop a running app.",
  "mobile.start_perf_session": "Start lightweight performance polling for one app.",
  "mobile.stop_perf_session": "Stop and summarize an existing performance session.",
  "mobile.get_perf_samples": "Fetch paginated performance samples from storage."
};

export const highRiskTools: ToolName[] = [];
