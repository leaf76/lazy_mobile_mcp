import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, "..");

function parseCsv(input: string | undefined): string[] {
  if (!input) {
    return [];
  }

  return input
    .split(",")
    .map((value) => value.trim())
    .filter((value) => value.length > 0);
}

export interface ServerConfig {
  pythonBin: string;
  pythonWorkerPath: string;
  allowlist: string[];
  sqlitePath: string;
  logLevel: "debug" | "info" | "warn" | "error";
}

export function loadConfig(): ServerConfig {
  return {
    pythonBin: process.env.PYTHON_BIN ?? "python3",
    pythonWorkerPath: process.env.PYTHON_WORKER_PATH ?? path.join(projectRoot, "python", "worker.py"),
    allowlist: parseCsv(process.env.DEVICE_ALLOWLIST),
    sqlitePath: process.env.SQLITE_PATH ?? path.join(projectRoot, "artifacts", "mobile.db"),
    logLevel: (process.env.LOG_LEVEL as ServerConfig["logLevel"] | undefined) ?? "info"
  };
}
