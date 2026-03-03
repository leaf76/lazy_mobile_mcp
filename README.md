# lazy-mobile-mcp

Local **Model Context Protocol (MCP)** server for **Android and iOS mobile automation** with **performance telemetry**.  
Control real devices and simulators using `screenshot`, `tap`, `swipe`, `input_text`, `launch_app`, and collect baseline metrics (`cpu`, `memory`, `launch time`) with session history in SQLite.

Keywords: MCP server, mobile automation, Android ADB automation, iOS simulator automation, WebDriverAgent, app performance telemetry.

## Why This Project

- Build a local MCP bridge for AI clients over `stdio`.
- Automate Android via ADB and iOS via `simctl` / `devicectl` / WDA.
- Keep operations traceable with `trace_id` in responses and logs.
- Persist sessions, samples, and artifacts in SQLite for reproducibility.

## Features

- `stdio` MCP transport for local AI tooling.
- Single active device model (`select_device`) with optional per-call `device_id`.
- Android adapter via ADB CLI.
- iOS adapter via Xcode tools with macOS guard and graceful degradation.
- WDA endpoint auto-discovery for iOS interactive actions.
- JSON logging and unified error contract.
- SQLite persistence for `sessions`, `perf_samples`, `artifacts`, `audit_logs`.

## Tool Index

- `mobile.list_devices`
- `mobile.select_device`
- `mobile.get_capabilities`
- `mobile.screenshot`
- `mobile.tap`
- `mobile.swipe`
- `mobile.input_text`
- `mobile.launch_app`
- `mobile.stop_app`
- `mobile.start_perf_session`
- `mobile.stop_perf_session`
- `mobile.get_perf_samples`

## Architecture

- TypeScript MCP server (tool contracts, validation, policy, trace ID)
- Python worker (device operations, adapters, storage, perf collector)
- Android adapter (`adb`)
- iOS adapter (`simctl`, `devicectl`, WDA)
- SQLite storage (`artifacts/mobile.db`)

## Prerequisites

- Node.js 20+
- Python 3.11+
- Android: `adb` in `PATH`
- iOS (optional): macOS + `xcrun` (`simctl`/`devicectl`)
- For iOS interactive actions (`tap/swipe/input`): reachable WebDriverAgent endpoint

## Install

```bash
npm install
python3 -m pip install -r python/requirements.txt
```

## Install From npm

```bash
npm install lazy_mobile_mcp
python3 -m pip install -r node_modules/lazy_mobile_mcp/python/requirements.txt
```

Run with `npx`:

```bash
npx lazy-mobile-mcp
```

Global install:

```bash
npm install -g lazy_mobile_mcp
python3 -m pip install -r "$(npm root -g)/lazy_mobile_mcp/python/requirements.txt"
lazy-mobile-mcp
```

## Run

Development:

```bash
npm run dev
```

Production:

```bash
npm run build
npm start
```

## Configuration

- `PYTHON_BIN` (default `python3`)
- `PYTHON_WORKER_PATH` (default `python/worker.py`)
- `SQLITE_PATH` (default `artifacts/mobile.db`)
- `DEVICE_ALLOWLIST` (comma-separated)
- `LOG_LEVEL` (`debug|info|warn|error`)
- `WDA_BASE_URL` (optional override for iOS WDA endpoint)

If `WDA_BASE_URL` is not set, the adapter probes common local endpoints (`127.0.0.1` / `localhost`, ports `8100/8101/8200/8201` + local listening ports).

## iOS Capability Notes

- Simulator: screenshot + launch/stop + WDA interactive actions.
- Physical device: launch/stop via `devicectl`; screenshot and interactive actions via WDA.
- Non-macOS host: iOS tools return `ERR_IOS_UNAVAILABLE_ON_HOST`.

## Testing

```bash
npm test
npm run test:py
```
