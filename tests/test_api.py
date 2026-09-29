"""Phase 5 tests: project, plan, and task API endpoints."""

from app.services.ai_planner import AIPlannerError, InvalidAIOutputError

E_COMMERCE_BRIEF = (
    "Build an e-commerce application where users can register, browse products, "
    "add products to a cart, and place orders."
)


def create_project(client, name="E-commerce", **extra):
    return client.post("/api/projects", json={"name": name, **extra})


def generate_plan(client, project_id, brief=E_COMMERCE_BRIEF):
    return client.post(f"/api/projects/{project_id}/generate-plan", json={"brief": brief})


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


def test_create_project(client):
    response = create_project(
        client, name="Todo App", description="A simple todo list", original_brief="Build a todo application."
    )
    assert response.status_code == 201
    data = response.json()
    assert data["id"] >= 1
    assert data["name"] == "Todo App"
    assert data["description"] == "A simple todo list"
    assert data["original_brief"] == "Build a todo application."
    assert data["created_at"] is not None
    assert data["updated_at"] is not None


def test_create_project_missing_name(client):
    assert create_project(client, name="").status_code == 422
    response = client.post("/api/projects", json={"description": "no name"})
    assert response.status_code == 422


def test_list_projects(client):
    create_project(client, name="First")
    create_project(client, name="Second")

    response = client.get("/api/projects")
    assert response.status_code == 200
    projects = response.json()
    assert len(projects) == 2
    assert projects[0]["name"] == "Second"  # newest first
    assert projects[0]["requirements_count"] == 0
    assert projects[0]["modules_count"] == 0
    assert projects[0]["tasks_count"] == 0


def test_get_project(client):
    created = create_project(client, name="Hospital System").json()
    response = client.get(f"/api/projects/{created['id']}")
    assert response.status_code == 200
    assert response.json()["name"] == "Hospital System"


def test_get_missing_project_404(client):
    assert client.get("/api/projects/999").status_code == 404


# ---------------------------------------------------------------------------
# Plan generation and retrieval
# ---------------------------------------------------------------------------


def test_generate_plan_end_to_end(client):
    project = create_project(client).json()
    response = generate_plan(client, project["id"])
    assert response.status_code == 200

    plan = response.json()
    assert plan["project"]["id"] == project["id"]
    assert plan["project"]["name"] == "E-commerce"
    assert len(plan["requirements"]) >= 1
    assert len(plan["modules"]) >= 1
    assert len(plan["tasks"]) >= 1
    for task in plan["tasks"]:
        assert task["title"]
        assert task["priority"] in {"HIGH", "MEDIUM", "LOW"}
        assert task["status"] == "TODO"
        assert isinstance(task["acceptance_criteria"], list)
        assert isinstance(task["module_name"], str)


def test_generate_plan_persists_to_database(client):
    project = create_project(client).json()
    generated = generate_plan(client, project["id"]).json()

    # The response carries database row ids.
    task_ids = {t["id"] for t in generated["tasks"]}
    assert all(tid >= 1 for tid in task_ids)
    for dep in generated["dependencies"]:
        assert dep["task_id"] in task_ids
        assert dep["depends_on_task_id"] in task_ids

    # The stored plan is retrievable and matches.
    stored = client.get(f"/api/projects/{project['id']}/plan")
    assert stored.status_code == 200
    stored_plan = stored.json()
    assert len(stored_plan["tasks"]) == len(generated["tasks"])
    assert len(stored_plan["modules"]) == len(generated["modules"])
    assert len(stored_plan["requirements"]) == len(generated["requirements"])
    assert len(stored_plan["dependencies"]) == len(generated["dependencies"])

    # Module task counts are real.
    for module in stored_plan["modules"]:
        tasks_in_module = [t for t in stored_plan["tasks"] if t["module_id"] == module["id"]]
        assert module["task_count"] == len(tasks_in_module)


def test_generate_plan_stores_brief_and_summary(client):
    project = create_project(client).json()
    generate_plan(client, project["id"])

    stored = client.get(f"/api/projects/{project['id']}").json()
    assert stored["original_brief"] == E_COMMERCE_BRIEF
    assert stored["description"]  # plan summary


def test_generate_plan_missing_project_404(client):
    response = client.post("/api/projects/999/generate-plan", json={"brief": E_COMMERCE_BRIEF})
    assert response.status_code == 404


def test_generate_plan_empty_brief_422(client):
    project = create_project(client).json()
    assert client.post(
        f"/api/projects/{project['id']}/generate-plan", json={"brief": ""}
    ).status_code == 422
    assert client.post(
        f"/api/projects/{project['id']}/generate-plan", json={"brief": "   "}
    ).status_code == 422


def test_generate_plan_very_short_brief_422(client):
    project = create_project(client).json()
    response = generate_plan(client, project["id"], brief="x")
    assert response.status_code == 422
    assert "too short" in response.json()["detail"]


def test_generate_plan_large_brief_422(client):
    project = create_project(client).json()
    response = generate_plan(client, project["id"], brief="Build an app. " + "x" * 20000)
    assert response.status_code == 422
    assert "too long" in response.json()["detail"]


def test_plan_not_generated_404(client):
    project = create_project(client).json()
    response = client.get(f"/api/projects/{project['id']}/plan")
    assert response.status_code == 404


def test_regenerate_replaces_previous_plan(client):
    project = create_project(client).json()
    first = generate_plan(client, project["id"]).json()
    second = generate_plan(client, project["id"]).json()

    assert len(second["tasks"]) == len(first["tasks"])
    stored = client.get(f"/api/projects/{project['id']}/plan").json()
    assert len(stored["tasks"]) == len(first["tasks"])

    # No orphaned rows: task ids are unique and stable in count.
    task_ids = [t["id"] for t in stored["tasks"]]
    assert len(set(task_ids)) == len(task_ids)


def test_generate_plan_ai_failure_returns_friendly_502(client, monkeypatch):
    project = create_project(client).json()

    import app.api.projects as projects_module

    def failing_planner(brief):
        raise AIPlannerError("upstream exploded")

    monkeypatch.setattr(projects_module, "plan_project", failing_planner)
    response = generate_plan(client, project["id"])
    assert response.status_code == 502
    assert "Unable to generate the project plan" in response.json()["detail"]
    assert "upstream exploded" not in response.json()["detail"]


def test_generate_plan_invalid_ai_output_returns_502(client, monkeypatch):
    project = create_project(client).json()

    import app.api.projects as projects_module

    def bad_planner(brief):
        raise InvalidAIOutputError("AI returned garbage")

    monkeypatch.setattr(projects_module, "plan_project", bad_planner)
    response = generate_plan(client, project["id"])
    assert response.status_code == 502
    assert "Unable to generate the project plan" in response.json()["detail"]


def test_generate_plan_value_error_returns_422(client, monkeypatch):
    project = create_project(client).json()

    import app.api.projects as projects_module

    monkeypatch.setattr(projects_module, "plan_project", lambda brief: (_ for _ in ()).throw(ValueError("bad brief")))
    response = generate_plan(client, project["id"], brief="Build an app.")
    assert response.status_code == 422
    assert "bad brief" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Task update / delete
# ---------------------------------------------------------------------------


def _generated_task(client):
    project = create_project(client).json()
    plan = generate_plan(client, project["id"]).json()
    return project, plan["tasks"][0]


def test_update_task(client):
    project, task = _generated_task(client)
    response = client.put(
        f"/api/tasks/{task['id']}",
        json={"title": "Renamed task", "priority": "LOW", "status": "IN_PROGRESS"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Renamed task"
    assert data["priority"] == "LOW"
    assert data["status"] == "IN_PROGRESS"
    assert data["id"] == task["id"]

    # Change persists in the stored plan.
    stored = client.get(f"/api/projects/{project['id']}/plan").json()
    updated = next(t for t in stored["tasks"] if t["id"] == task["id"])
    assert updated["title"] == "Renamed task"
    assert updated["status"] == "IN_PROGRESS"


def test_update_task_partial_fields_only(client):
    project, task = _generated_task(client)
    response = client.put(f"/api/tasks/{task['id']}", json={"description": "New details"})
    data = response.json()
    assert data["description"] == "New details"
    assert data["title"] == task["title"]
    assert data["priority"] == task["priority"]


def test_update_task_invalid_priority_422(client):
    _, task = _generated_task(client)
    response = client.put(f"/api/tasks/{task['id']}", json={"priority": "URGENT"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, str)  # friendly single-string message, no error list
    assert "HIGH" in detail


def test_update_task_invalid_status_422(client):
    _, task = _generated_task(client)
    response = client.put(f"/api/tasks/{task['id']}", json={"status": "WHATEVER"})
    assert response.status_code == 422


def test_update_task_empty_title_422(client):
    _, task = _generated_task(client)
    response = client.put(f"/api/tasks/{task['id']}", json={"title": ""})
    assert response.status_code == 422
    assert "too short" in response.json()["detail"]


def test_update_missing_task_404(client):
    response = client.put("/api/tasks/999", json={"title": "x"})
    assert response.status_code == 404


def test_update_task_acceptance_criteria_replaces(client):
    project, task = _generated_task(client)
    response = client.put(
        f"/api/tasks/{task['id']}",
        json={"acceptance_criteria": ["New criterion A", "New criterion B"]},
    )
    assert response.status_code == 200
    criteria = response.json()["acceptance_criteria"]
    assert [c["criterion"] for c in criteria] == ["New criterion A", "New criterion B"]
    assert criteria[0]["id"] != criteria[1]["id"]

    stored = client.get(f"/api/projects/{project['id']}/plan").json()
    updated = next(t for t in stored["tasks"] if t["id"] == task["id"])
    assert [c["criterion"] for c in updated["acceptance_criteria"]] == [
        "New criterion A",
        "New criterion B",
    ]


def test_delete_task(client):
    project, task = _generated_task(client)
    response = client.delete(f"/api/tasks/{task['id']}")
    assert response.status_code == 204
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 404

    stored = client.get(f"/api/projects/{project['id']}/plan").json()
    task_ids = [t["id"] for t in stored["tasks"]]
    assert task["id"] not in task_ids


def test_database_failure_returns_friendly_503(client, monkeypatch):
    """Database failures never leak internals to users."""
    project = create_project(client).json()

    import app.api.projects as projects_module
    from sqlalchemy.exc import SQLAlchemyError

    def failing_persist(db, project, plan, original_brief=None):
        raise SQLAlchemyError("disk full")

    monkeypatch.setattr(projects_module, "persist_plan", failing_persist)
    response = generate_plan(client, project["id"])
    assert response.status_code == 503
    assert "Database error" in response.json()["detail"]
    assert "disk full" not in response.json()["detail"]


def test_generate_plan_persists_ai_generated_status(client, monkeypatch):
    """The status produced by the planner is stored, not always TODO."""
    from app.schemas import (
        PlanDependency,
        PlanModule,
        PlanProject,
        PlanRequirement,
        PlanTask,
        ProjectPlan,
    )

    project = create_project(client).json()
    plan = ProjectPlan(
        project=PlanProject(name="Status App", summary="Explicit statuses."),
        requirements=[PlanRequirement(id=1, title="Core")],
        modules=[PlanModule(id=1, name="Core")],
        tasks=[
            PlanTask(
                id=1,
                module_id=1,
                requirement_id=1,
                title="Build schema",
                priority="HIGH",
                status="IN_PROGRESS",
            ),
            PlanTask(
                id=2,
                module_id=1,
                requirement_id=1,
                title="Build API",
                priority="HIGH",
            ),
        ],
        dependencies=[PlanDependency(task_id=2, depends_on=1)],
    )

    import app.api.projects as projects_module

    monkeypatch.setattr(projects_module, "plan_project", lambda brief: plan)
    response = generate_plan(client, project["id"])
    assert response.status_code == 200

    by_title = {t["title"]: t for t in response.json()["tasks"]}
    assert by_title["Build schema"]["status"] == "IN_PROGRESS"
    assert by_title["Build API"]["status"] == "TODO"  # default when absent

    stored = client.get(f"/api/projects/{project['id']}/plan").json()
    stored_by_title = {t["title"]: t for t in stored["tasks"]}
    assert stored_by_title["Build schema"]["status"] == "IN_PROGRESS"
    assert stored_by_title["Build API"]["status"] == "TODO"


def test_ai_invalid_output_never_reaches_database(client, monkeypatch):
    """A plan missing AI fields must be rejected before storage."""
    project = create_project(client).json()

    import app.api.projects as projects_module

    def bad_planner(brief):
        # Simulates an AI response missing required fields.
        raise InvalidAIOutputError("AI output failed plan validation")

    monkeypatch.setattr(projects_module, "plan_project", bad_planner)
    response = generate_plan(client, project["id"])
    assert response.status_code == 502

    # Nothing was stored.
    assert client.get(f"/api/projects/{project['id']}/plan").status_code == 404


def test_delete_depended_on_task_removes_edges(client):
    """Deleting a task others depend on must not leave dangling edges."""
    project = create_project(client).json()
    plan = generate_plan(client, project["id"]).json()

    # Find a task that other tasks depend on (fallback chains tasks per module).
    depended_on = None
    for dep in plan["dependencies"]:
        depended_on = dep["depends_on_task_id"]
        break
    assert depended_on is not None

    response = client.delete(f"/api/tasks/{depended_on}")
    assert response.status_code == 204

    stored = client.get(f"/api/projects/{project['id']}/plan").json()
    remaining = [t["id"] for t in stored["tasks"]]
    assert depended_on not in remaining
    for dep in stored["dependencies"]:
        assert dep["task_id"] not in {depended_on}
        assert dep["depends_on_task_id"] not in {depended_on}
        assert dep["task_id"] in remaining
        assert dep["depends_on_task_id"] in remaining
