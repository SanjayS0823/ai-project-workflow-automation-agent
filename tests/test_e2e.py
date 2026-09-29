"""Phase 10: complete end-to-end workflow tests.

Covers the full loop for each test brief:

    Create Project -> Enter Brief -> Generate Plan -> AI Analysis
    -> Validation -> Database Storage -> Dashboard -> Open Task
    -> Edit Task -> Save -> Reload -> Verify Persistence

Plus failure scenarios: empty brief, invalid request, AI failure, and
invalid AI response.
"""

import pytest

from app.services.ai_planner import AIPlannerError, InvalidAIOutputError

TEST_BRIEFS = [
    (
        "e-commerce",
        "Build an e-commerce application where users can register, browse "
        "products, add products to a cart, and place orders.",
    ),
    (
        "hospital",
        "Build a hospital appointment system where patients can register, "
        "search for doctors, view available slots, and book appointments.",
    ),
    (
        "todo",
        "Build a todo application.",
    ),
]


@pytest.mark.parametrize("label,brief", TEST_BRIEFS, ids=[t[0] for t in TEST_BRIEFS])
def test_full_workflow(client, label, brief):
    """The complete workflow, end to end, for one brief."""
    # 1. Create project
    created = client.post(
        "/api/projects",
        json={"name": f"{label.title()} Project", "original_brief": brief},
    )
    assert created.status_code == 201
    project = created.json()
    project_id = project["id"]

    # 2-4. Enter brief -> generate plan (AI analysis) -> validation -> storage
    generated = client.post(
        f"/api/projects/{project_id}/generate-plan", json={"brief": brief}
    )
    assert generated.status_code == 200
    plan = generated.json()

    assert plan["project"]["id"] == project_id
    assert plan["project"]["name"] == f"{label.title()} Project"
    assert len(plan["requirements"]) >= 1
    assert len(plan["modules"]) >= 1
    assert len(plan["tasks"]) >= 1

    task_ids = {t["id"] for t in plan["tasks"]}
    for dependency in plan["dependencies"]:
        assert dependency["task_id"] in task_ids
        assert dependency["depends_on_task_id"] in task_ids

    for task in plan["tasks"]:
        assert task["title"]
        assert task["priority"] in {"HIGH", "MEDIUM", "LOW"}
        assert task["status"] == "TODO"
        assert len(task["acceptance_criteria"]) >= 1

    # 5. Database storage is retrievable and consistent.
    stored = client.get(f"/api/projects/{project_id}/plan")
    assert stored.status_code == 200
    assert len(stored.json()["tasks"]) == len(plan["tasks"])
    assert len(stored.json()["modules"]) == len(plan["modules"])

    project_row = client.get(f"/api/projects/{project_id}").json()
    assert project_row["original_brief"] == brief
    assert project_row["description"]  # plan summary stored

    listing = client.get("/api/projects").json()
    row = next(p for p in listing if p["id"] == project_id)
    assert row["tasks_count"] == len(plan["tasks"])
    assert row["requirements_count"] == len(plan["requirements"])
    assert row["modules_count"] == len(plan["modules"])

    # 6-9. Open a task -> edit -> save.
    task = plan["tasks"][0]
    new_title = f"{task['title']} (human reviewed)"
    new_criteria = ["Updated acceptance criterion A.", "Updated acceptance criterion B."]
    updated = client.put(
        f"/api/tasks/{task['id']}",
        json={
            "title": new_title,
            "description": "Adjusted by a human planner after AI generation.",
            "priority": "LOW",
            "status": "DONE",
            "acceptance_criteria": new_criteria,
        },
    )
    assert updated.status_code == 200
    saved = updated.json()
    assert saved["id"] == task["id"]
    assert saved["title"] == new_title
    assert saved["priority"] == "LOW"
    assert saved["status"] == "DONE"

    # 10. Reload (fresh request, equivalent to reloading the page) and verify.
    reloaded = client.get(f"/api/projects/{project_id}/plan").json()
    reloaded_task = next(t for t in reloaded["tasks"] if t["id"] == task["id"])
    assert reloaded_task["title"] == new_title
    assert reloaded_task["priority"] == "LOW"
    assert reloaded_task["status"] == "DONE"
    assert [c["criterion"] for c in reloaded_task["acceptance_criteria"]] == new_criteria


# ---------------------------------------------------------------------------
# Failure scenarios
# ---------------------------------------------------------------------------


def test_e2e_empty_brief(client):
    project = client.post("/api/projects", json={"name": "Empty Brief"}).json()
    response = client.post(
        f"/api/projects/{project['id']}/generate-plan", json={"brief": ""}
    )
    assert response.status_code == 422
    # Nothing was stored.
    assert client.get(f"/api/projects/{project['id']}/plan").status_code == 404


def test_e2e_invalid_request(client):
    # Missing required project name.
    assert client.post("/api/projects", json={}).status_code == 422
    # Malformed JSON body.
    response = client.post(
        "/api/projects",
        content=b"{not valid json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)


def test_e2e_ai_failure(client, monkeypatch):
    import app.api.projects as projects_module

    project = client.post("/api/projects", json={"name": "AI Failure"}).json()

    def failing_planner(brief):
        raise AIPlannerError("upstream outage")

    monkeypatch.setattr(projects_module, "plan_project", failing_planner)
    response = client.post(
        f"/api/projects/{project['id']}/generate-plan",
        json={"brief": "Build a todo application."},
    )
    assert response.status_code == 502
    assert "Unable to generate the project plan" in response.json()["detail"]
    assert "upstream outage" not in response.json()["detail"]
    assert client.get(f"/api/projects/{project['id']}/plan").status_code == 404


def test_e2e_invalid_ai_response(client, monkeypatch):
    import app.api.projects as projects_module

    project = client.post("/api/projects", json={"name": "Invalid AI Response"}).json()

    def garbage_planner(brief):
        raise InvalidAIOutputError("AI returned schema-invalid JSON")

    monkeypatch.setattr(projects_module, "plan_project", garbage_planner)
    response = client.post(
        f"/api/projects/{project['id']}/generate-plan",
        json={"brief": "Build a todo application."},
    )
    assert response.status_code == 502
    assert client.get(f"/api/projects/{project['id']}/plan").status_code == 404


def test_e2e_no_broken_plan_after_partial_failure(client, monkeypatch):
    """A project keeps working even when a later regeneration fails."""
    import app.api.projects as projects_module

    project = client.post(
        "/api/projects", json={"name": "Resilient"}
    ).json()
    ok = client.post(
        f"/api/projects/{project['id']}/generate-plan",
        json={"brief": "Build a todo application."},
    )
    assert ok.status_code == 200
    original_count = len(ok.json()["tasks"])

    def failing_planner(brief):
        raise AIPlannerError("outage during regeneration")

    monkeypatch.setattr(projects_module, "plan_project", failing_planner)
    failed = client.post(
        f"/api/projects/{project['id']}/generate-plan",
        json={"brief": "Build a todo application."},
    )
    assert failed.status_code == 502

    # The previously stored plan is untouched.
    stored = client.get(f"/api/projects/{project['id']}/plan")
    assert stored.status_code == 200
    assert len(stored.json()["tasks"]) == original_count
