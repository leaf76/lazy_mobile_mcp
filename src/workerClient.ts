import { createInterface } from "node:readline";
import { ChildProcessWithoutNullStreams, spawn } from "node:child_process";
import { AppError } from "./errors.js";
import { Logger } from "./logger.js";

interface WorkerRequest {
  id: number;
  method: string;
  params: Record<string, unknown>;
  trace_id: string;
}

interface WorkerResult {
  [key: string]: unknown;
}

interface WorkerError {
  error: string;
  code: string;
  trace_id: string;
}

interface WorkerResponse {
  id: number;
  result?: WorkerResult;
  error?: WorkerError;
}

interface PendingCall {
  resolve: (value: WorkerResult) => void;
  reject: (error: Error) => void;
  timeout: NodeJS.Timeout;
}

export interface WorkerClientOptions {
  pythonBin: string;
  scriptPath: string;
  sqlitePath: string;
  logger: Logger;
}

export class WorkerClient {
  private process?: ChildProcessWithoutNullStreams;
  private readonly pending = new Map<number, PendingCall>();
  private nextId = 1;

  constructor(private readonly options: WorkerClientOptions) {}

  async start(): Promise<void> {
    if (this.process) {
      return;
    }

    const child = spawn(this.options.pythonBin, [this.options.scriptPath], {
      env: {
        ...process.env,
        SQLITE_PATH: this.options.sqlitePath
      },
      stdio: ["pipe", "pipe", "pipe"]
    });

    child.on("exit", (code, signal) => {
      this.options.logger.error("worker-exit", {
        code,
        signal
      });
      this.rejectAllPending(
        new AppError({
          message: "Python worker exited unexpectedly",
          code: "ERR_WORKER_EXITED",
          category: "dependency",
          traceId: "worker-process"
        })
      );
      this.process = undefined;
    });

    child.stderr.on("data", (chunk: Buffer) => {
      const text = chunk.toString("utf-8").trim();
      if (text.length > 0) {
        this.options.logger.info("worker-log", { line: text });
      }
    });

    const rl = createInterface({ input: child.stdout });
    rl.on("line", (line) => {
      this.handleResponseLine(line);
    });

    this.process = child;
  }

  async stop(): Promise<void> {
    if (!this.process) {
      return;
    }

    this.process.kill("SIGTERM");
    this.process = undefined;
  }

  async call(method: string, params: Record<string, unknown>, traceId: string): Promise<WorkerResult> {
    if (!this.process) {
      throw new AppError({
        message: "Python worker is not started",
        code: "ERR_WORKER_NOT_STARTED",
        category: "system",
        traceId
      });
    }

    const id = this.nextId;
    this.nextId += 1;

    const request: WorkerRequest = {
      id,
      method,
      params,
      trace_id: traceId
    };

    const payload = JSON.stringify(request);

    return new Promise<WorkerResult>((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(
          new AppError({
            message: `Python worker timeout for method: ${method}`,
            code: "ERR_WORKER_TIMEOUT",
            category: "dependency",
            traceId
          })
        );
      }, 10000);

      this.pending.set(id, { resolve, reject, timeout });
      this.process?.stdin.write(`${payload}\n`);
    });
  }

  private handleResponseLine(line: string): void {
    let response: WorkerResponse;

    try {
      response = JSON.parse(line) as WorkerResponse;
    } catch {
      this.options.logger.warn("worker-invalid-json", { line });
      return;
    }

    const pendingCall = this.pending.get(response.id);
    if (!pendingCall) {
      this.options.logger.warn("worker-response-without-pending", { id: response.id });
      return;
    }

    this.pending.delete(response.id);
    clearTimeout(pendingCall.timeout);

    if (response.error) {
      pendingCall.reject(
        new AppError({
          message: response.error.error,
          code: response.error.code,
          category: "dependency",
          traceId: response.error.trace_id
        })
      );
      return;
    }

    pendingCall.resolve(response.result ?? {});
  }

  private rejectAllPending(error: Error): void {
    for (const [id, pendingCall] of this.pending.entries()) {
      clearTimeout(pendingCall.timeout);
      pendingCall.reject(error);
      this.pending.delete(id);
    }
  }
}
