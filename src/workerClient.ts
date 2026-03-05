import { AppError } from "./errors.js";
import { Logger } from "./logger.js";
import { Worker } from "./worker.js";

interface WorkerResult {
  [key: string]: unknown;
}

export interface WorkerClientOptions {
  sqlitePath: string;
  allowlist: string[];
  logger: Logger;
  adbBin: string;
  wdaBaseUrl?: string;
}

export class WorkerClient {
  private worker?: Worker;

  constructor(private readonly options: WorkerClientOptions) {}

  async start(): Promise<void> {
    if (this.worker) {
      return;
    }

    this.worker = new Worker({
      sqlitePath: this.options.sqlitePath,
      allowlist: this.options.allowlist,
      adbBin: this.options.adbBin,
      wdaBaseUrl: this.options.wdaBaseUrl
    });

    this.options.logger.info("worker-started", {
      sqlite_path: this.options.sqlitePath,
      adb_bin: this.options.adbBin
    });
  }

  async stop(): Promise<void> {
    if (!this.worker) {
      return;
    }

    this.worker = undefined;
    this.options.logger.info("worker-stopped", {});
  }

  async call(method: string, params: Record<string, unknown>, traceId: string): Promise<WorkerResult> {
    if (!this.worker) {
      throw new AppError({
        message: "Worker is not started",
        code: "ERR_WORKER_NOT_STARTED",
        category: "system",
        traceId
      });
    }

    return await new Promise<WorkerResult>((resolve, reject) => {
      const timeout = setTimeout(() => {
        reject(
          new AppError({
            message: `Worker timeout for method: ${method}`,
            code: "ERR_WORKER_TIMEOUT",
            category: "dependency",
            traceId
          })
        );
      }, 10_000);

      try {
        const result = this.worker?.handle(method, params, traceId) ?? {};
        clearTimeout(timeout);
        resolve(result);
      } catch (error: unknown) {
        clearTimeout(timeout);

        if (error instanceof Error) {
          reject(error);
          return;
        }

        reject(
          new AppError({
            message: "Unknown worker call error",
            code: "ERR_INTERNAL",
            category: "system",
            traceId
          })
        );
      }
    });
  }
}
