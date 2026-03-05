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
  allowlist: string[];
  sqlitePath: string;
  logLevel: "debug" | "info" | "warn" | "error";
  adbBin: string;
  wdaBaseUrl?: string;
}

export function loadConfig(): ServerConfig {
  return {
    allowlist: parseCsv(process.env.DEVICE_ALLOWLIST),
    sqlitePath: process.env.SQLITE_PATH ?? path.join(projectRoot, "artifacts", "mobile.db"),
    logLevel: (process.env.LOG_LEVEL as ServerConfig["logLevel"] | undefined) ?? "info",
    adbBin: process.env.ADB_BIN ?? "adb",
    wdaBaseUrl: process.env.WDA_BASE_URL
  };
}
