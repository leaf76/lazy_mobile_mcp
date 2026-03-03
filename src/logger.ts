export type LogLevel = "debug" | "info" | "warn" | "error";

const levelPriority: Record<LogLevel, number> = {
  debug: 10,
  info: 20,
  warn: 30,
  error: 40
};

export class Logger {
  constructor(private readonly minLevel: LogLevel = "info") {}

  log(level: LogLevel, event: string, payload: Record<string, unknown>): void {
    if (levelPriority[level] < levelPriority[this.minLevel]) {
      return;
    }

    const line = JSON.stringify({
      ts: new Date().toISOString(),
      level,
      event,
      ...payload
    });

    process.stderr.write(`${line}\n`);
  }

  debug(event: string, payload: Record<string, unknown>): void {
    this.log("debug", event, payload);
  }

  info(event: string, payload: Record<string, unknown>): void {
    this.log("info", event, payload);
  }

  warn(event: string, payload: Record<string, unknown>): void {
    this.log("warn", event, payload);
  }

  error(event: string, payload: Record<string, unknown>): void {
    this.log("error", event, payload);
  }
}
