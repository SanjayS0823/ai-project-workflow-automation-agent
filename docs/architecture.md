# Architecture

## Overview

The application is a three-layer, single-process system: a React SPA talks over
HTTP/JSON to a FastAPI backend, which persists structured plans in SQLite via
SQLAlchemy. There are no microservices, message brokers, or external services
other than the optional LLM API and the optional GitHub API.

```
┌────────────────────────────┐        ┌─────────────────────────────┐
│  React + Vite + TypeScript │  /api  │  FastAPI (backend/app)       │
│  frontend/src              │ ─────▶ │  api/ (routes + serializers) │
│  (dev proxy /api → :8000)  │ ◀───── │  services/ (business logic)  │
└────────────────────────────┘        └──────────────┬──────────────┘
                                                     │ SQLAlchemy
                                            ┌────────▼────────┐
                                            │  SQLite (app.db)│
                                            └─────────────────┘
```

## Layers

### Frontend (`frontend/src`)

- `api.ts` — typed fetch client. Every request is wrapped; non-2xx responses
  surface the backend `detail` string as an `ApiError`, and network failures
  map to a friendly message. The UI therefore never shows raw errors or crashes
  on API failures.
- `pages/` — `HomePage` (project list + create/generate form),
  `DashboardPage` (stats, tabs, filters), `TaskReviewPage` (task detail + edit
  + GitHub export).
- `components/` — `Layout` (sidebar shell), presentational pieces (tables,
  badges, tabs, spinner, forms).
- Routing is client-side (react-router). Dashboard tabs sync with the `?tab=`
  query parameter so the sidebar can deep-link into any tab.
- The Vite dev server proxies `/api` to the backend, so the SPA uses
  same-origin requests in development.

### Backend (`backend/app`)

- `main.py` — application factory: creates the FastAPI app, initializes the
  database on startup (lifespan), registers routers, and installs two global
  exception handlers:
  - `RequestValidationError` → friendly single-string `422` detail (no raw
    pydantic error arrays).
  - `SQLAlchemyError` → `503` "Database error. Please try again." (no internal
    details).
- `api/` — thin route modules (`projects.py`, `tasks.py`) plus
  `serializers.py`, which maps ORM rows to response schemas (including module
  and requirement names, criteria, dependency ids, and the GitHub issue URL).
- `services/` — the business logic:
  - `ai_planner.py` — real planner backed by Google's Gemini API (official
    `google-genai` SDK, `response_mime_type=application/json` and temperature
    0.2), typed errors, brief validation, mode selection (`AI_USE_FALLBACK`),
    and **automatic fallback**: when Gemini fails (config/auth/quota/timeout/
    network/malformed output) `plan_project()` logs the failure and uses the
    deterministic fallback planner instead.
  - `prompts.py` — system prompt and brief→JSON-schema user prompt. The
    prompt demands strict JSON-only output (markdown/prose/code fences are
    rejected) and enforces planning quality: scope grounded in the brief, 3–8
    requirements and modules adapted to complexity, specific/actionable tasks
    with priority + status + 1–3 acceptance criteria each, unique ids with
    resolvable references, no duplicate tasks, and dependencies in realistic
    implementation order (schema → API → UI → dashboard).
  - `fallback_planner.py` — deterministic keyword-based planner used only when
    `AI_USE_FALLBACK=1`; explicitly separated from the real implementation.
  - `plan_storage.py` — maps a validated `ProjectPlan` (plan-local ids) to
    database rows (real ids) and replaces the previous plan on regeneration.
  - `github_integration.py` — optional GitHub issue export using `urllib`;
    idempotent, never automatic.

## The AI planning pipeline

```
brief ─▶ _validate_brief (non-empty, ≥10 chars)
      ─▶ plan_project()
            ├─ AI_USE_FALLBACK=1 → fallback_planner (Gemini never called)
            └─ else → GeminiPlanner (env: AI_LLM_API_KEY/BASE_URL/MODEL/TIMEOUT)
                 ─▶ models.generate_content(json mime, temperature 0.2)
                 ─▶ JSON parse
                 ─▶ ProjectPlan.model_validate()  ← cross-field checks:
                                                      unique ids, resolvable
                                                      module/requirement/task
                                                      refs, no self-dependency,
                                                      valid priority + status
                 └─ AIPlannerError (auth/quota/timeout/network/malformed/
                      invalid output) → log warning → fallback_planner
      ─▶ persist_plan()  (only after validation succeeds)

Plans carry an initial task `status` (TODO/IN_PROGRESS/BLOCKED/DONE) generated
by the model (most work starts as TODO); `persist_plan()` stores it instead of
hardcoding TODO. Invalid priority/status values fail validation before
storage.
```

Key properties: **an invalid AI response is never stored** (invalid Gemini
output is discarded and the always-validated fallback plan is used instead),
and only AI-provider errors trigger the fallback — database, persistence, and
request-validation failures are handled outside `plan_project()` and never
fall back.

## Persistence model

Six tables (see `backend/app/models.py`):

- `projects` → `requirements`, `modules`, `tasks` (one-to-many)
- `tasks` → `acceptance_criteria` (one-to-many), and self-references through
  `task_dependencies` (`task_id` depends on `depends_on_task_id`)
- All foreign keys are `ON DELETE CASCADE`; ORM relationships use
  `delete-orphan` cascades so deleting a project/task removes its children.
- `ck_task_no_self_dependency` CHECK constraint rejects `task_id ==
  depends_on_task_id` at the database level (the schema validates it too).
- SQLite foreign-key enforcement (`PRAGMA foreign_keys=ON`) is enabled for
  every connection — orphaned rows are rejected, not silently allowed.

Plan regeneration deletes the project's existing plan rows (tasks first, then
modules, then requirements) and inserts the new plan in one transaction.

## Error handling strategy

All user-facing errors are single-string `{"detail": "..."}` responses:

| Condition | Status |
| --- | --- |
| Validation failure (missing/short/long/invalid fields) | `422` |
| Missing project / task / plan not generated | `404` |
| Unexpected AI planner failure (Gemini failure normally auto-falls back) | `502` |
| GitHub not configured | `503` |
| GitHub API/network failure | `502` |
| Database failure | `503` |

The frontend displays these strings inline and adds its own fallbacks for
network-level failures.

## Optional GitHub integration

```
Task review page → user clicks "Create GitHub issue" → window.confirm
→ POST /api/tasks/{id}/github-issue
→ create_issue_for_task(): returns existing URL if present (idempotent)
→ POST https://api.github.com/repos/{GITHUB_REPO}/issues
→ html_url stored on task (tasks.github_issue_url) and shown as a link
```

Issues are **only** created through this explicit user action. Plan generation
never calls GitHub (verified by a dedicated test).

## Testing strategy

- Backend: pytest with an in-memory SQLite database per test (foreign keys
  enabled) and a FastAPI `TestClient` with overridden DB dependency. The AI
  planner is tested with a fake Gemini client (success, provider errors,
  malformed/invalid output) and the automatic-fallback path is covered at
  `plan_project()` level; the GitHub integration with a stubbed `_post_issue`.
- Frontend: TypeScript compilation (`tsc -b`), Vite build, and oxlint. Live
  flows are exercised via headless-browser DOM checks and API-level E2E tests.

See [testing.md](testing.md).
