# API Reference

Base URL: `http://localhost:8000` (development). Interactive docs:
`http://localhost:8000/docs` (OpenAPI at `/openapi.json`).

All request/response bodies are JSON. Errors always have the shape
`{"detail": "<message>"}` — never stack traces.

- `422` — validation failed (friendly single-string detail)
- `404` — project/task not found, or plan not generated yet
- `502` — upstream AI or GitHub failure
- `503` — database failure, or GitHub integration not configured

## Service endpoints

### `GET /`

Service metadata.

```json
{ "message": "AI Project & Workflow Automation Agent API", "status": "running" }
```

### `GET /health`

Health check.

```json
{ "status": "healthy" }
```

## Projects

### `POST /api/projects` — create a project

Request:

```json
{
  "name": "E-commerce Platform",
  "description": "Optional description",
  "original_brief": "Optional original brief"
}
```

`name` is required (1–200 chars); `description` and `original_brief` are
optional. Status: `201 Created`.

Response (`ProjectOut`):

```json
{
  "id": 1,
  "name": "E-commerce Platform",
  "description": null,
  "original_brief": null,
  "created_at": "2026-08-12T15:00:00",
  "updated_at": "2026-08-12T15:00:00"
}
```

### `GET /api/projects` — list projects

Returns projects newest-first. Each entry is `ProjectOut` plus live child
counts (`ProjectListOut`):

```json
[
  {
    "id": 1,
    "name": "E-commerce Platform",
    "description": "…",
    "original_brief": "…",
    "created_at": "…",
    "updated_at": "…",
    "requirements_count": 3,
    "modules_count": 3,
    "tasks_count": 6
  }
]
```

### `GET /api/projects/{project_id}` — get a project

`404` if the project does not exist. Response: `ProjectOut`.

### `POST /api/projects/{project_id}/generate-plan` — generate and store an AI plan

Request:

```json
{ "brief": "Build an e-commerce application where users can register, browse products, add products to a cart, and place orders." }
```

`brief` is required, 10–20000 characters.

Pipeline: brief → Gemini planner (with automatic fallback to the deterministic
planner on any AI-provider failure) → Pydantic `ProjectPlan` validation →
store requirements, modules, tasks, acceptance criteria, and dependencies
(replacing any previous plan) → return the stored plan. Gemini failures are
logged internally; the request still returns a valid plan.

Status codes:

| Code | Meaning |
| --- | --- |
| `200` | Plan generated, stored, and returned |
| `404` | Project not found |
| `422` | Brief empty / too short / too long |
| `502` | Unexpected AI planner failure (normally auto-falls back, so rare) |
| `503` | Database failure |

Response (`ProjectPlanResponse`):

```json
{
  "project": { "id": 1, "name": "E-commerce Platform", "description": "…", "original_brief": "…", "created_at": "…", "updated_at": "…" },
  "requirements": [ { "id": 1, "title": "User accounts", "description": "…" } ],
  "modules": [ { "id": 1, "name": "Accounts", "description": "…", "task_count": 2 } ],
  "tasks": [
    {
      "id": 1,
      "project_id": 1,
      "module_id": 1,
      "requirement_id": 1,
      "title": "Implement user registration",
      "description": "…",
      "priority": "HIGH",
      "status": "TODO",
      "created_at": "…",
      "updated_at": "…",
      "module_name": "Accounts",
      "requirement_title": "User accounts",
      "acceptance_criteria": [ { "id": 1, "criterion": "Users can register." } ],
      "dependencies": [],
      "github_issue_url": null
    }
  ],
  "dependencies": [ { "task_id": 2, "depends_on_task_id": 1 } ]
}
```

Notes:

- `priority` is `HIGH` | `MEDIUM` | `LOW`; `status` is `TODO` |
  `IN_PROGRESS` | `BLOCKED` | `DONE`. The AI planner sets the initial status
  (most planned work starts as `TODO`; the model may set others when the
  brief implies existing work). The fallback planner always produces `TODO`.
  Either way, `status` values are validated before storage.
- Task `dependencies` lists the ids this task depends on; the top-level
  `dependencies` array lists all edges.

### `GET /api/projects/{project_id}/plan` — return the stored plan

`404` if the project does not exist **or** no plan has been generated yet.
Response: `ProjectPlanResponse`.

## Tasks

### `PUT /api/tasks/{task_id}` — update a task

Only provided fields are changed:

```json
{
  "title": "Implement registration with email",
  "description": "Optional new description",
  "priority": "HIGH",
  "status": "IN_PROGRESS",
  "acceptance_criteria": ["Users can register.", "Errors are shown clearly."]
}
```

All fields are optional. `title` (1–300 chars), `priority`, and `status` are
validated; `acceptance_criteria`, when provided, **replaces** the existing
list.

Status codes: `200` (returns `TaskOut`) · `404` task not found · `422` invalid
field values.

### `DELETE /api/tasks/{task_id}` — delete a task

`204 No Content` on success (acceptance criteria and dependency edges are
removed). `404` if the task does not exist.

### `POST /api/tasks/{task_id}/github-issue` — create a GitHub issue (optional)

Creates a GitHub issue from the task (title, description, module/requirement
context, acceptance criteria) in the configured repository. **Explicitly
triggered by the user only; never automatic.** Idempotent — if the task
already has an issue URL, it is returned without calling GitHub again.

Status codes:

| Code | Meaning |
| --- | --- |
| `200` | Returns `TaskOut` with `github_issue_url` populated |
| `404` | Task not found |
| `502` | GitHub API/network failure (friendly message) |
| `503` | `GITHUB_TOKEN`/`GITHUB_REPO` not configured |

## TaskOut shape

```json
{
  "id": 1,
  "project_id": 1,
  "module_id": 1,
  "requirement_id": 1,
  "title": "…",
  "description": "…",
  "priority": "HIGH",
  "status": "TODO",
  "created_at": "…",
  "updated_at": "…",
  "module_name": "Accounts",
  "requirement_title": "User accounts",
  "acceptance_criteria": [ { "id": 1, "criterion": "…" } ],
  "dependencies": [2],
  "github_issue_url": "https://github.com/zeneralabs/sandbox/issues/42"
}
```
