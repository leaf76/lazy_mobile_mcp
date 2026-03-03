# AGENTS.md

DO NOT FORGET
- Follow DEFAULT FLOW unless explicitly allowed.
- SECURITY rules are ALWAYS ON.
- UI / UX rules apply to all user-facing changes.
- If unsure, ask before coding.

LANGUAGE
- English only for code, comments, logs, config, UI strings, commit messages.
- Planning and explanations: Traditional Chinese (Taiwan).

CORE RULES
- If requirements or constraints are unclear, ask BEFORE coding.
- Do NOT modify, revert, delete, or refactor unrelated code or files.
- Do NOT remove or revert changes without explicit user approval.
- No hardcoded secrets, credentials, or environment-specific config.
- No SQL string concatenation. All SQL must be parameterized.
- No silent error swallowing. No bare catch/except.
- Do NOT experiment directly in production.

DEFAULT FLOW
Clarify → Plan → TDD → Implement → Summary
- For trivial or UI-only changes, Plan/TDD may be abbreviated but not skipped silently.

SKILL STRATEGY (UI/UX)
- For UI/UX tasks, always try Gemini-based UIUX skills first (`gemini-uiux-designer`, `gemini-uiux-visual-engineer`).
- If Gemini execution fails, fallback to non-Gemini UI/UX flow.
- Failure is defined as any of:
  - Tool unavailable / dispatch error / exception.
  - Timeout: invocation is actually terminated by timeout, or finishes with no usable result.
  - Dependency error (quota/auth/network/authz, e.g. HTTP 429) returned by Gemini.
  - Empty output, clearly malformed output, or missing required deliverables.
- Tool window: 10 seconds per Gemini invocation (soft decision window, not a hard kill timeout).
  - If usable output arrives after 10 seconds and the invocation completes successfully, treat it as success (not timeout).
  - If classification is ambiguous, use final process result (exit status/stdout/stderr) as source of truth.
- On failure: retry Gemini once; if the second attempt also fails, perform one fallback attempt to non-Gemini flow.
- Use fallback only after these failed attempts; do not bypass Gemini for normal UI/UX tasks.

SKILL ROUTING POLICY (NON-SYSTEM)
- Do not change `.system` skills (`skill-creator`, `skill-installer`) from this plan.
- Keep `.system` skills unchanged unless explicitly requested.
- For non-system skills, follow `/Users/cy76/.codex/skills/README.md` as the single source of truth:
  - `explore` is the default entrypoint for codebase investigation.
  - `document-writer` handles general documentation; `doc` handles DOCX-specific work.
  - `frontend-ui-ux-engineer` handles Web/frontend UIUX; `frontend-mobile-uiux-designer` handles iOS/Android scope.
  - Gemini skills are used as first-pass helpers under UI/UX flows, with retry/fallback policy unchanged.

CLARIFY
- Ask concise questions only if scope, acceptance criteria, or constraints are unclear.
- Ask before proceeding if a breaking change, data migration, or security impact is possible.
- Do not propose solutions or plans at this stage.

PLAN
- Then briefly state (include only what’s relevant):
  - Goal and explicit non-goals
  - Files/modules likely to change
  - Risk notes (compatibility, security, data, migrations)
  - Test strategy (what level, what to mock)
  - Verification plan (how to prove it works)
  - Rollback approach (how to undo safely)
- No code or tests in this section.

TDD
- If TDD is skipped, explicitly state why and how correctness is verified.
- Write tests BEFORE implementation for business logic and critical paths.
- Auth, payments, permissions, and data mutation require TDD plus integration tests.
- For UI-only changes, TDD is optional but a verification plan is required.
- Tests must be deterministic and isolated (Arrange, Act, Assert).

IMPLEMENT
- Search existing code before adding new logic.
- Keep changes minimal, scoped, and single-responsibility.
- Preserve existing style, types, lint, and format rules.
- No commented-out, dead, or unrelated refactor code.

SUMMARY
- Summary of changes (what / where / why).
- List of updated files.
- Test results or reproducible validation steps.
- Compatibility impact (only if applicable).
- Rollback notes and follow-up optimizations (if relevant).

SECURITY (ALWAYS ON)
- Secrets from Secret Manager or environment variables only.
- Least-privilege access.
- Validate all external input.
- Never log secrets, tokens, or PII.

LOGGING & TRACEABILITY (WHEN SERVER-SIDE OR INTEGRATIONS ARE INVOLVED)
- Use X-Request-ID if provided; otherwise generate UUID v4.
- Trace ID must appear in all logs and error responses.
- Logs must be JSON in production.

ERROR RESPONSE (WHEN API/SERVER-SIDE)
- Returned to clients only.
- Internal logs may contain more details but must reference the same trace_id.
```json
{
  "error": "Human readable message",
  "code": "ERR_xxx",
  "trace_id": "uuid-v4"
}
```

ERROR HANDLING (WHEN APPLICABLE)
- Classify errors (validation, business, system, dependency).
- Log stack traces for system errors.
- Retry only idempotent operations.
- Use bounded exponential backoff.
- Define timeouts (API ~10s, DB ~5s).

TASK-TYPE CHECKLISTS (CONDITIONAL)
FRONTEND (USER-FACING UI: WEB / ANDROID / IOS)
- Verify key user flows using appropriate tools:
  - Web: DevTools
  - Android: adb / Android Studio
  - iOS: Xcode / Simulator
- Ensure user-facing errors are clear and actionable.
- Avoid leaking technical or internal details to users.

UI / UX (WHEN USER-FACING)
- Do NOT change UI/UX behavior without explicit intent or approval.
- Preserve existing interaction patterns unless a change is explicitly required.
- All user-visible states must be handled:
  - Loading
  - Empty
  - Error
  - Disabled
  - Success (if applicable)

- User feedback must be:
  - Immediate for user actions
  - Clear and human-readable
  - Consistent with existing tone and terminology

- Avoid UI regressions:
  - No layout shifts during loading (where reasonably preventable)
  - No breaking keyboard / touch interactions
  - No degraded accessibility compared to existing behavior

- Error presentation:
  - User-facing messages must not expose technical details
  - Map internal errors to user-meaningful messages
  - Retry guidance must be explicit if retry is possible

- Performance perception:
  - Avoid blocking UI on non-critical operations
  - Prefer optimistic or incremental rendering when applicable

APP (mobile)
- Applies in addition to FRONTEND (USER-FACING UI: WEB / ANDROID / IOS).
- Assume unreliable networks and background suspension.
- Avoid infinite retries; keep retries bounded and idempotent.
- Note impacts to auth/session/storage, push, deep links, permissions.
- Consider backward compatibility with older app versions when calling APIs.

BACKEND
- Do NOT break API contracts without versioning or approval.
- Prefer backward-compatible changes.
- DB schema changes require safe rollout (expand, migrate, contract).
- Ensure error codes and trace_id are returned where relevant.

INFRA / OPS
- State what will change (resources, config, permissions) and blast radius.
- Provide a minimal troubleshooting note (where to look first if it fails).
- Avoid high-cardinality logs/metrics that can explode cost.

FILES
- Check file size before reading (wc -l).
- Use partial reads (rg, sed, jq, yq).
- Do not dump large files blindly.

TESTING
- During any manual testing (DevTools, adb, iOS tools, emulators, real devices), always verify:
  1) Functionality: core flows work without errors
  2) UI/UX: layout, feedback, and interactions are usable
  3) Regressions: no new obvious breakage introduced

- If UI/App related:
  - Check loading, error, and disabled states
  - Verify behavior under slow or unstable network

- If Backend/API related:
  - Validate responses, error codes, and trace_id on failure

- If no automated tests exist, provide clear manual verification steps.

## Skills
A skill is a set of local instructions to follow that is stored in a `SKILL.md` file. Below is the list of skills that can be used. Each entry includes a name, description, and file path so you can open the source for full instructions when using a specific skill.
### Available skills
- adb-android-app-ops: Operate and monitor Android apps/devices via adb (Android Debug Bridge): list/select devices, install/uninstall APKs, start/stop/clear apps, send intents/deep links, simulate input (tap/swipe/text/keyevent), capture screenshots/screen recordings, dump UI hierarchy, and collect diagnostics (logcat crash/ANR, dumpsys meminfo/cpu/activity). Use when a task needs adb commands or repeatable adb automation from the terminal. (file: /Users/cy76/.codex/skills/public/adb-android-app-ops/SKILL.md)
- atlas: macOS-only AppleScript control for the ChatGPT Atlas desktop app. Use only when the user explicitly asks to control Atlas tabs/bookmarks/history on macOS and the "ChatGPT Atlas" app is installed; do not trigger for general browser tasks or non-macOS environments. (file: /Users/cy76/.codex/skills/atlas/SKILL.md)
- chrome-devtools-test: Use the Chrome DevTools MCP tools to do lightweight E2E checks, capture console/network issues, and gather performance traces. Use when asked to “test in browser”, “verify UI”, or “debug in DevTools”. (file: /Users/cy76/.codex/skills/chrome-devtools-test/SKILL.md)
- cloudflare-deploy: Deploy applications and infrastructure to Cloudflare using Workers, Pages, and related platform services. Use when the user asks to deploy, host, publish, or set up a project on Cloudflare. (file: /Users/cy76/.codex/skills/cloudflare-deploy/SKILL.md)
- create-plan: Create a concise plan. Use when a user explicitly asks for a plan related to a coding task. (file: /Users/cy76/.codex/skills/create-plan/SKILL.md)
- debug-memory-leak: Debug memory leaks in the application (file: /Users/cy76/.codex/skills/debug-memory-leak/SKILL.md)
- develop-web-game: Use when Codex is building or iterating on a web game (HTML/JS) and needs a reliable development + testing loop: implement small changes, run a Playwright-based test script with short input bursts and intentional pauses, inspect screenshots/text, and review console errors with render_game_to_text. (file: /Users/cy76/.codex/skills/develop-web-game/SKILL.md)
- doc: Use when the task involves reading, creating, or editing `.docx` documents, especially when formatting or layout fidelity matters; prefer `python-docx` plus the bundled `scripts/render_docx.py` for visual checks. (file: /Users/cy76/.codex/skills/doc/SKILL.md)
- document-writer: Orchestration role for producing clear, accurate documentation. Use when writing ADRs, runbooks, specs, README updates, release notes, or user-facing docs that must match repo conventions. (file: /Users/cy76/.codex/skills/public/document-writer/SKILL.md)
- explore: Orchestration role for exploring a codebase quickly and safely. Use when you need entry points, dependency maps, hypotheses, and a proposed approach before implementation. (file: /Users/cy76/.codex/skills/public/explore/SKILL.md)
- figma: Use the Figma MCP server to fetch design context, screenshots, variables, and assets from Figma, and to translate Figma nodes into production code. Trigger when a task involves Figma URLs, node IDs, design-to-code implementation, or Figma MCP setup and troubleshooting. (file: /Users/cy76/.codex/skills/figma/SKILL.md)
- firmware-feature-writer: Use when implementing, debugging, or refactoring embedded firmware features (C/C++/Rust). Focus on deterministic behavior, peripheral/register correctness, RTOS/task safety, and testability on constrained devices. (file: /Users/cy76/.codex/skills/firmware-feature-writer/SKILL.md)
- fix-bug: Systematically reproduce, find root cause, and fix bugs (RCA-first) with TDD and regression verification. Use when a user reports a bug or something behaves incorrectly. (file: /Users/cy76/.codex/skills/fix-bug/SKILL.md)
- fix-lint: Fix formatting/lint issues safely across common stacks (Rust/TypeScript/Python/Go). Use when CI fails on lint/format, or when asked to “fix lint/format”. (file: /Users/cy76/.codex/skills/fix-lint/SKILL.md)
- frontend-mobile-uiux-designer: Design native iOS+Android product UX from brief to developer-ready UI specs. Use for mobile UX flows and IA, wireframes (prefer Pencil .pen), UI component/state specs, design tokens, and implementation notes for iOS/Android engineers. (file: /Users/cy76/.codex/skills/public/frontend-mobile-uiux-designer/SKILL.md)
- frontend-ui-ux-engineer: Orchestration role for frontend UI/UX design and implementation. Use when designing user-facing flows, UI components, and CSS/layout changes; start with Gemini-assisted UX planning, then implement with minimal, safe code changes. (file: /Users/cy76/.codex/skills/public/frontend-ui-ux-engineer/SKILL.md)
- gemini-cli-imagegen: Generate images with local Gemini CLI. Use for text to image output, batch generation, and deterministic local image export workflows. (file: /Users/cy76/.codex/skills/gemini-cli-imagegen/SKILL.md)
- gemini-uiux-designer: Plan UI/UX and frontend design direction using the local Gemini CLI, with implementation-ready handoff outputs (IA, flows, layout system, component specs, states, and tokens). Use when the user wants Gemini-powered ideation or a concrete frontend design plan/spec. (file: /Users/cy76/.codex/skills/gemini-uiux-designer/SKILL.md)
- gemini-uiux-visual-engineer: Optimize and plan UI/UX using the local Gemini CLI, producing implementation-ready "visual engineering" artifacts (UX audit, prioritized backlog, IA, user flows, screen specs, component inventory, design tokens, microcopy, rollout/experiment plans). Use when the user asks to improve usability/conversion/accessibility/consistency, plan IA/flows/screens for a new feature/product, or turn rough ideas into actionable frontend tasks and tokens. (file: /Users/cy76/.codex/skills/gemini-uiux-visual-engineer/SKILL.md)
- image-file-reader: Read files and images in automation-friendly way when multimodal parsing is not available. Use for OCR on screenshots, extracting text from PDFs/TXT/JSON/CSV, and returning structured output for downstream processing. Use when you need deterministic, local file inspection instead of model vision. (file: /Users/cy76/.codex/skills/public/image-file-reader/SKILL.md)
- imagegen: Use when the user asks to generate or edit images via the OpenAI Image API (for example: generate image, edit/inpaint/mask, background removal or replacement, transparent background, product shots, concept art, covers, or batch variants); run the bundled CLI (`scripts/image_gen.py`) and require `OPENAI_API_KEY` for live calls. (file: /Users/cy76/.codex/skills/imagegen/SKILL.md)
- multimodal-looker: Orchestration role for image and UI inspection. Use when analyzing screenshots, UI states, diagrams, logs captured as images, or visual regressions to produce structured findings and next debugging steps. (file: /Users/cy76/.codex/skills/public/multimodal-looker/SKILL.md)
- openai-docs: Use when the user asks how to build with OpenAI products or APIs and needs up-to-date official documentation with citations (for example: Codex, Responses API, Chat Completions, Apps SDK, Agents SDK, Realtime, model capabilities or limits); prioritize OpenAI docs MCP tools and restrict any fallback browsing to official OpenAI domains. (file: /Users/cy76/.codex/skills/openai-docs/SKILL.md)
- plan-mode: Enforce a concise multi-step execution plan before coding or running commands for any non-trivial task. Trigger when the user says plan-mode/先規劃 or when work spans multiple steps, files, or carries risk. (file: /Users/cy76/.codex/skills/plan-mode/SKILL.md)
- playwright: Use when the task requires automating a real browser from the terminal (navigation, form filling, snapshots, screenshots, data extraction, UI-flow debugging) via `playwright-cli` or the bundled wrapper script. (file: /Users/cy76/.codex/skills/playwright/SKILL.md)
- project-planning: Create a comprehensive project plan (goals, milestones, timeline, risks, resources). Use when starting a new project or planning significant changes. (file: /Users/cy76/.codex/skills/project-planning/SKILL.md)
- review-changes: Review uncommitted git changes (staged and unstaged) and provide actionable feedback on code quality, security, and best practices. Use before committing code, during code review, or when validating changes before pushing. (file: /Users/cy76/.codex/skills/review-changes/SKILL.md)
- rust-programmer: Write, refactor, and debug Rust (.rs) code and Cargo projects using idiomatic patterns, safe error handling, ownership/lifetimes guidance, async/concurrency best practices, and a standard verification routine (fmt/clippy/test). Use when tasks involve Rust source files, Cargo.toml workspaces, Rust API design, or Rust performance/safety reviews. (file: /Users/cy76/.codex/skills/rust-programmer/SKILL.md)
- screenshot: Use when the user explicitly asks for a desktop or system screenshot (full screen, specific app or window, or a pixel region), or when tool-specific capture capabilities are unavailable and an OS-level capture is needed. (file: /Users/cy76/.codex/skills/screenshot/SKILL.md)
- security-threat-model: Repository-grounded threat modeling that enumerates trust boundaries, assets, attacker capabilities, abuse paths, and mitigations, and writes a concise Markdown threat model. Trigger only when the user explicitly asks to threat model a codebase or path, enumerate threats/abuse paths, or perform AppSec threat modeling. Do not trigger for general architecture summaries, code review, or non-security design work. (file: /Users/cy76/.codex/skills/security-threat-model/SKILL.md)
- yeet: Use only when the user explicitly asks to stage, commit, push, and open a GitHub pull request in one flow using the GitHub CLI (`gh`). (file: /Users/cy76/.codex/skills/yeet/SKILL.md)
- skill-creator: Guide for creating effective skills. This skill should be used when users want to create a new skill (or update an existing skill) that extends Codex's capabilities with specialized knowledge, workflows, or tool integrations. (file: /Users/cy76/.codex/skills/.system/skill-creator/SKILL.md)
- skill-installer: Install Codex skills into $CODEX_HOME/skills from a curated list or a GitHub repo path. Use when a user asks to list installable skills, install a curated skill, or install a skill from another repo (including private repos). (file: /Users/cy76/.codex/skills/.system/skill-installer/SKILL.md)
### How to use skills
- Discovery: The list above is the skills available in this session (name + description + file path). Skill bodies live on disk at the listed paths.
- Trigger rules: If the user names a skill (with `$SkillName` or plain text) OR the task clearly matches a skill's description shown above, you must use that skill for that turn. Multiple mentions mean use them all. Do not carry skills across turns unless re-mentioned.
- Missing/blocked: If a named skill isn't in the list or the path can't be read, say so briefly and continue with the best fallback.
- How to use a skill (progressive disclosure):
  1) After deciding to use a skill, open its `SKILL.md`. Read only enough to follow the workflow.
  2) When `SKILL.md` references relative paths (e.g., `scripts/foo.py`), resolve them relative to the skill directory listed above first, and only consider other paths if needed.
  3) If `SKILL.md` points to extra folders such as `references/`, load only the specific files needed for the request; don't bulk-load everything.
  4) If `scripts/` exist, prefer running or patching them instead of retyping large code blocks.
  5) If `assets/` or templates exist, reuse them instead of recreating from scratch.
- Coordination and sequencing:
  - If multiple skills apply, choose the minimal set that covers the request and state the order you'll use them.
  - Announce which skill(s) you're using and why (one short line). If you skip an obvious skill, say why.
- Context hygiene:
  - Keep context small: summarize long sections instead of pasting them; only load extra files when needed.
  - Avoid deep reference-chasing: prefer opening only files directly linked from `SKILL.md` unless you're blocked.
  - When variants exist (frameworks, providers, domains), pick only the relevant reference file(s) and note that choice.
- Safety and fallback: If a skill can't be applied cleanly (missing files, unclear instructions), state the issue, pick the next-best approach, and continue.
