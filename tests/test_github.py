"""Phase 12 tests: GitHub issue integration."""

import pytest

from app.models import AcceptanceCriterion, Module, Project, Requirement, Task
from app.services import github_integration
from app.services.github_integration import (
    GitHubIntegrationError,
    GitHubNotConfiguredError,
    create_issue_for_task,
)

E_COMMERCE_BRIEF = (
    "Build an e-commerce application where users can register, browse products, "
    "add products to a cart, and place orders."
)


def _make_task(db_session) -> Task:
    project = Project(name="E-commerce", original_brief=E_COMMERCE_BRIEF)
    task = Task(
        project=project,
        title="Implement user registration",
        description="Create the signup flow with validation.",
        priority="HIGH",
    )
    db_session.add_all([project, task])
    db_session.flush()
    db_session.add(AcceptanceCriterion(task=task, criterion="Users can register."))
    db_session.commit()
    return task


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


def test_create_issue_success(monkeypatch, db_session):
    captured = {}

    def fake_post(owner_repo, token, title, body):
        captured.update(owner_repo=owner_repo, token=token, title=title, body=body)
        return "https://github.com/zeneralabs/sandbox/issues/1"

    monkeypatch.setattr(github_integration, "_post_issue", fake_post)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test-token")
    monkeypatch.setenv("GITHUB_REPO", "zeneralabs/sandbox")

    task = _make_task(db_session)
    url = create_issue_for_task(task)

    assert url == "https://github.com/zeneralabs/sandbox/issues/1"
    assert captured["owner_repo"] == "zeneralabs/sandbox"
    assert captured["title"] == "Implement user registration"
    assert "Acceptance criteria" in captured["body"]
    assert "Users can register." in captured["body"]
    assert "**Project:** E-commerce" in captured["body"]


def test_create_issue_idempotent_skips_api(monkeypatch, db_session):
    calls = []

    def fake_post(*args):
        calls.append(args)
        return "https://github.com/x/y/issues/1"

    monkeypatch.setattr(github_integration, "_post_issue", fake_post)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPO", "o/r")

    task = _make_task(db_session)
    task.github_issue_url = "https://github.com/o/r/issues/9"
    db_session.commit()

    url = create_issue_for_task(task)
    assert url == "https://github.com/o/r/issues/9"
    assert calls == []


def test_not_configured(monkeypatch, db_session):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    task = _make_task(db_session)
    with pytest.raises(GitHubNotConfiguredError, match="not configured"):
        create_issue_for_task(task)


def test_api_failure_wrapped(monkeypatch, db_session):
    def boom(*args):
        raise GitHubIntegrationError("rate limited")

    monkeypatch.setattr(github_integration, "_post_issue", boom)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPO", "o/r")

    task = _make_task(db_session)
    with pytest.raises(GitHubIntegrationError, match="rate limited"):
        create_issue_for_task(task)


def test_issue_body_includes_module_and_requirement(db_session):
    task = _make_task(db_session)
    task.module = Module(project=task.project, name="Accounts")
    task.requirement = Requirement(project=task.project, title="User accounts")
    db_session.commit()

    body = github_integration._issue_body(task)
    assert "**Module:** Accounts" in body
    assert "**Requirement:** User accounts" in body
    assert "**Project:** E-commerce" in body


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


def _generated_task(client):
    project = client.post("/api/projects", json={"name": "E-commerce"}).json()
    plan = client.post(
        f"/api/projects/{project['id']}/generate-plan", json={"brief": E_COMMERCE_BRIEF}
    ).json()
    return project, plan["tasks"][0]


def test_api_create_issue_flow(client, monkeypatch):
    from app.services import github_integration

    def fake_post(owner_repo, token, title, body):
        return "https://github.com/zeneralabs/sandbox/issues/42"

    monkeypatch.setattr(github_integration, "_post_issue", fake_post)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_x")
    monkeypatch.setenv("GITHUB_REPO", "zeneralabs/sandbox")

    project, task = _generated_task(client)
    response = client.post(f"/api/tasks/{task['id']}/github-issue")
    assert response.status_code == 200
    data = response.json()
    assert data["github_issue_url"] == "https://github.com/zeneralabs/sandbox/issues/42"

    # Persisted and visible in the stored plan.
    stored = client.get(f"/api/projects/{project['id']}/plan").json()
    stored_task = next(t for t in stored["tasks"] if t["id"] == task["id"])
    assert stored_task["github_issue_url"] == "https://github.com/zeneralabs/sandbox/issues/42"


def test_api_create_issue_not_configured(client, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPO", raising=False)

    _, task = _generated_task(client)
    response = client.post(f"/api/tasks/{task['id']}/github-issue")
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]
    # Nothing was stored.
    assert response.json()["detail"]


def test_api_create_issue_failure_502(client, monkeypatch):
    from app.services import github_integration

    def boom(*args):
        raise GitHubIntegrationError("rate limited")

    monkeypatch.setattr(github_integration, "_post_issue", boom)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPO", "o/r")

    _, task = _generated_task(client)
    response = client.post(f"/api/tasks/{task['id']}/github-issue")
    assert response.status_code == 502
    assert "Unable to create the GitHub issue" in response.json()["detail"]
    assert "rate limited" not in response.json()["detail"]


def test_api_create_issue_missing_task_404(client):
    assert client.post("/api/tasks/999/github-issue").status_code == 404


def test_plan_generation_never_creates_issues(client, monkeypatch):
    """AI plan generation must never trigger GitHub issue creation."""
    from app.services import github_integration

    calls = []

    def fake_post(*args):
        calls.append(args)
        return "https://github.com/x/y/issues/1"

    monkeypatch.setattr(github_integration, "_post_issue", fake_post)
    monkeypatch.setenv("GITHUB_TOKEN", "t")
    monkeypatch.setenv("GITHUB_REPO", "o/r")

    project = client.post("/api/projects", json={"name": "E-commerce"}).json()
    client.post(
        f"/api/projects/{project['id']}/generate-plan", json={"brief": E_COMMERCE_BRIEF}
    )
    assert calls == []

    plan = client.get(f"/api/projects/{project['id']}/plan").json()
    assert all(t["github_issue_url"] is None for t in plan["tasks"])
