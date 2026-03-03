# Security Notes

## Controls

- Device allowlist enforced via `DEVICE_ALLOWLIST`.
- High-risk operations require explicit `confirm=true` and `reason`.
- Error payloads are client-safe and include `trace_id` only.
- Logs are JSON and avoid secrets/PII by default.

## Operational Guidance

- Use least-privilege host users for running the server.
- Restrict local machine access; this server can trigger device actions.
- Store secrets only in environment variables or secret managers.
- Do not commit environment-specific credentials.

## Traceability

- Every request has a `trace_id`.
- The same `trace_id` appears in:
  - tool error response
  - TypeScript and Python log lines
  - session metadata where applicable
