# Runbook

## Quick Health Checks

1. Confirm MCP server starts:
```bash
npm run dev
```

2. Confirm worker init and DB creation:
```bash
ls artifacts/mobile.db
```

3. Confirm Android tooling:
```bash
adb devices
```

4. Confirm iOS tooling (macOS only):
```bash
xcrun xctrace list devices
xcrun devicectl list devices
```

## Common Issues

### `ERR_IOS_UNAVAILABLE_ON_HOST`
- Cause: iOS tools requested on non-macOS host.
- Action: run server on macOS or use Android-only workflows.

### `ERR_DEVICE_NOT_ALLOWED`
- Cause: device ID not in allowlist.
- Action: update `DEVICE_ALLOWLIST` env var.

### `ERR_WORKER_TIMEOUT`
- Cause: long-running adapter command or blocked tool.
- Action: inspect stderr JSON logs and command-level errors.

### SQLite lock contention
- Cause: concurrent writes beyond busy timeout.
- Action: reduce polling frequency; ensure one server process per DB file.

## First places to inspect

- TypeScript stderr JSON logs from MCP process.
- Node worker logs (`worker-started`, `worker-stopped`, and tool/error events).
- `artifacts/mobile.db` with:
```bash
sqlite3 artifacts/mobile.db '.tables'
```
