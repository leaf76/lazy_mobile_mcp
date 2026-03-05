import { parseSetupCodexArgs, runSetupCodex, setupCodexUsage } from "./setupCodex.js";

function usage(): string {
  return [
    "Usage:",
    "  lazy-mobile-mcp                 Start MCP server over stdio",
    "  lazy-mobile-mcp setup-codex     Register this MCP in Codex",
    "",
    setupCodexUsage()
  ].join("\n");
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const command = args[0] ?? "";

  if (command === "" || command === undefined) {
    await import("./index.js");
    return;
  }

  if (command === "--help" || command === "-h") {
    process.stdout.write(`${usage()}\n`);
    return;
  }

  if (command !== "setup-codex") {
    process.stderr.write(`Unknown command: ${command}\n`);
    process.stderr.write("Run 'lazy-mobile-mcp --help' for usage.\n");
    process.exitCode = 1;
    return;
  }

  const setupArgs = args.slice(1);
  if (setupArgs.includes("--help") || setupArgs.includes("-h")) {
    process.stdout.write(`${setupCodexUsage()}\n`);
    return;
  }

  const options = parseSetupCodexArgs(setupArgs);
  runSetupCodex(options);
}

main().catch((error: unknown) => {
  if (error instanceof Error) {
    process.stderr.write(`${error.message}\n`);
  } else {
    process.stderr.write("Unknown CLI error\n");
  }
  process.exit(1);
});
