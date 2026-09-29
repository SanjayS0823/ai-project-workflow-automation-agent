# Testing

## Running the tests

```bash
# Backend (from the repository root; requires .venv with requirements-dev.txt)
.venv/bin/pytest tests/

# Frontend (typecheck, lint, and production build)
cd frontend
npm run lint
npm run build
```

The backend suite needs `pytest` and `httpx` (FastAPI `TestClient`), both in
`backend/requirements-dev.txt`.

## Backend suites

| File | Scope |
| --- | --- |
| `tests/conftest.py` | Fixtures: an in-memory SQLite session per test (foreign keys on) and a FastAPI `TestClient` backed by an isolated in-memory DB with the fallback planner enabled |
| `tests/test_database.py` | ORM models: CRUD, relationships, cascades (project/task deletion), integrity — self-dependency rejected, FK enforcement, required fields |
| `tests/test_schemas.py` | Plan schema validation: required fields, priority values, data types, unique ids, resolvable module/requirement/task references, no self-dependency |
| `tests/test_ai_planner.py` | Fallback planner (grounded plans, valid output, ordered dependencies); mode selection (`AI_USE_FALLBACK`, fallback mode skips Gemini); prompt quality (strict JSON-only, planning rules, dependency example); mocked Gemini planner — request shape, model override, valid JSON, invalid JSON, schema-invalid output, invalid priority/status, duplicate ids, unknown dependency reference, self-dependency output, empty content, malformed response, auth/quota/permission/server/timeout/network wrapping, status parsing/defaulting, brief validation; **automatic fallback** — Gemini success uses the Gemini plan, and auth/quota/timeout/network/malformed-JSON/invalid-plan/missing-key all fall back to the validated fallback plan with a logged warning; non-AI exceptions do NOT fall back |
| `tests/test_api.py` | All endpoints: project CRUD, generate/store/retrieve plan, regeneration, task update (partial, validation, criteria replacement), task delete (incl. depended-on tasks), error handling — friendly 422/502/503, nothing stored on AI failure |
| `tests/test_e2e.py` | Complete workflows for three briefs (create → generate → validate → store → list → edit → save → reload → verify persistence) plus failure scenarios |
| `tests/test_github.py` | GitHub export: issue body/content, idempotency, not-configured, API failure wrapping, endpoint flow, and the **no-automatic-creation** guard |

## End-to-end scenarios

For each brief below the full loop is exercised through the API:

```
Create Project -> Enter Brief -> Generate Plan -> AI Analysis
-> Validation -> Database Storage -> Dashboard -> Open Task
-> Edit Task -> Save -> Reload -> Verify Persistence
```

1. **e-commerce** — "Build an e-commerce application where users can register,
   browse products, add products to a cart, and place orders."
2. **hospital** — "Build a hospital appointment system where patients can
   register, search for doctors, view available slots, and book
   appointments."
3. **todo** — "Build a todo application."

Failure scenarios covered: empty brief, invalid request (missing name,
malformed JSON), AI failure, invalid AI response, and a failed regeneration
leaving the previously stored plan intact. A dedicated API test proves that a
planner-provided task status is persisted (and that an absent status defaults
to `TODO`).

## What is not covered by automation

- **Real Gemini planning** — the live-model path is exercised only through a
  mocked client (no API key in CI/local). Validate output quality with a real
  key before relying on generated plans. The automatic-fallback behavior is
  fully covered by mocks.
- **Real GitHub issue creation** — the integration is tested with a stubbed
  `_post_issue`. Creating a real issue requires `GITHUB_TOKEN` +
  `GITHUB_REPO` and the explicit UI flow.
- **Frontend interaction tests** — no Playwright/Cypress suite; the UI is
  verified by TypeScript compilation, lint, the production build, and manual
  end-to-end runs (including headless-browser DOM checks against the live
  stack).

## Manual smoke test (fallback)

```bash
# Terminal 1 — backend with the fallback planner
cd ai-project-workflow-automation-agent
AI_USE_FALLBACK=1 .venv/bin/uvicorn app.main:app --reload --port 8000 --app-dir backend

# Terminal 2 — frontend
cd frontend && npm run dev
```

Then in the browser: create a project with a brief → generate the plan → open
the dashboard tabs → open a task → edit and save → reload to confirm
persistence.

## Manual real-AI test

Requires `AI_USE_FALLBACK=0` and configured `AI_LLM_API_KEY` (a Gemini key
from https://aistudio.google.com/apikey) plus optional `AI_LLM_BASE_URL` /
`AI_LLM_MODEL` (set in `.env` or the shell — never print the key).

```bash
# Terminal 1 — backend with the real AI
cd ai-project-workflow-automation-agent
.venv/bin/uvicorn app.main:app --reload --port 8000 --app-dir backend

# Terminal 2 — frontend
cd frontend && npm run dev
```

Use the **Smart Campus Event Management System** brief (see `README.md`,
"Manual real-AI test") and verify: project created · requirements/modules/
tasks generated · priorities valid · statuses valid · dependencies valid ·
acceptance criteria present · dashboard displays the plan · task editing
persists across reloads · GitHub issue creation still works · invalid AI
output is never stored. To verify **automatic fallback**, temporarily set an
invalid/empty key with `AI_USE_FALLBACK=0` and confirm the plan still
generates while the backend log shows "automatically using the fallback
planner". The end-to-end pipeline (generation, validation, storage, review,
editing) is otherwise covered by the automated suites with a mocked client —
this manual run is the only step that needs a live model.
