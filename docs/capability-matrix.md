# Capability Matrix

| Capability | Android (ADB) | iOS Simulator (macOS) | iOS Physical (macOS) | Non-macOS Host |
|---|---|---|---|---|
| list devices | ✅ | ✅ | ✅ | iOS ❌ (`ERR_IOS_UNAVAILABLE_ON_HOST`) |
| select device | ✅ | ✅ | ✅ | iOS ❌ |
| screenshot | ✅ | ✅ (`auto-boot + simctl`) | ⚠️ via WDA endpoint | iOS ❌ |
| tap/swipe/input | ✅ | ⚠️ requires WDA session | ⚠️ requires WDA session | iOS ❌ |
| launch/stop app | ✅ | ✅ (`simctl`) | ✅ (`devicectl process`) | iOS ❌ |
| cpu/memory/launch metrics | ✅ baseline | ✅ baseline placeholder | ✅ baseline placeholder | iOS ❌ |
| fps/jank | planned | unsupported | unsupported | unsupported |

Notes:
- iOS control beyond launch/stop app requires WebDriverAgent (explicit `WDA_BASE_URL` or auto-discovered local endpoint).
- The current iOS adapter supports physical app lifecycle via `devicectl` and Simulator lifecycle via `simctl`.
- Simulator screenshot auto-boots the target simulator before capture.
- Physical screenshot requires a reachable WDA endpoint (explicit `WDA_BASE_URL` or auto-discovered local endpoint) and uses WDA `/screenshot`.
- WDA actions (`tap/swipe/input`) now use per-device session management with automatic session recreation on invalid session errors.
- When `WDA_BASE_URL` is not provided, adapter attempts automatic local WDA discovery.
- Capability-based parity is enforced: unsupported fields are explicitly marked.
