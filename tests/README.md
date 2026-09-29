# Tests

Backend tests run with `pytest`. Run from the repository root with:

```bash
.venv/bin/pytest tests/
```

## Suites

| File | Phase | Covers |
| --- | --- | --- |
| `test_database.py` | 2 | Models, relationships, cascades, integrity (self-dependency, FK enforcement) |
| `test_schemas.py` | 3 | Plan schema validation: required fields, priorities, types, references |
| `test_ai_planner.py` | 4 | Fallback planner, mode selection, mocked AI success/failure/timeout/invalid output |
| `test_api.py` | 5/9 | Project/plan/task endpoints, error handling, friendly messages |
| `test_e2e.py` | 10 | Complete end-to-end workflows + failure scenarios |
| `test_github.py` | 12 | GitHub issue export: service, API flow, safety |

## End-to-end scenarios (`test_e2e.py`)

The full workflow for each brief:

```
Create Project -> Enter Brief -> Generate Plan -> AI Analysis
-> Validation -> Database Storage -> Dashboard -> Open Task
-> Edit Task -> Save -> Reload -> Verify Persistence
```

Test briefs:

1. **e-commerce** — "Build an e-commerce application where users can register,
   browse products, add products to a cart, and place orders."
2. **hospital** — "Build a hospital appointment system where patients can
   register, search for doctors, view available slots, and book appointments."
3. **todo** — "Build a todo application."

Failure scenarios also covered: empty brief (`422`, nothing stored), invalid
request (missing name, malformed JSON → `422`), AI failure (`502` friendly
message, nothing stored), invalid AI response (`502`, nothing stored), and a
failed regeneration leaving the previously stored plan intact.
