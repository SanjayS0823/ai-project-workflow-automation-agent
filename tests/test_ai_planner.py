"""AI planner tests: Gemini (mocked google-genai client), automatic fallback,
and the deterministic development fallback planner."""

import json
import logging
from types import SimpleNamespace

import pytest

from app.schemas import ProjectPlan
from app.services.ai_planner import (
    AIPlannerConfigurationError,
    AIPlannerError,
    GeminiPlanner,
    InvalidAIOutputError,
    plan_project,
    use_fallback,
)
from app.services.fallback_planner import generate_fallback_plan


# ---------------------------------------------------------------------------
# Fallback planner
# ---------------------------------------------------------------------------

BRIEFS = {
    "ecommerce": (
        "Build an e-commerce application where users can register, browse "
        "products, add products to a cart, and place orders.",
        ["registration", "cart", "order"],
    ),
    "hospital": (
        "Build a hospital appointment system where patients can register, "
        "search for doctors, view available slots, and book appointments.",
        ["search for doctors", "appointment", "book"],
    ),
    "todo": (
        "Build a todo application.",
        ["todo"],
    ),
}


@pytest.mark.parametrize("brief,expected", list(BRIEFS.values()), ids=list(BRIEFS.keys()))
def test_fallback_plan_is_valid_and_grounded(brief, expected):
    plan = generate_fallback_plan(brief)
    # Re-validates against the schema (the strict path the API relies on).
    ProjectPlan.model_validate(plan.model_dump())

    assert plan.project.name
    assert len(plan.tasks) > 0
    assert len(plan.modules) > 0
    assert len(plan.requirements) > 0

    all_text = " ".join(t.title.lower() for t in plan.tasks)
    for keyword in expected:
        assert keyword in all_text, f"expected task title containing {keyword!r}"


def test_fallback_generic_brief_still_returns_valid_plan():
    plan = generate_fallback_plan("Build a helpful internal tool for the ops team.")
    ProjectPlan.model_validate(plan.model_dump())
    assert len(plan.tasks) >= 1
    assert plan.project.name


def test_fallback_rejects_empty_brief():
    with pytest.raises(ValueError):
        generate_fallback_plan("   ")


def test_fallback_dependencies_are_internal_and_ordered():
    plan = generate_fallback_plan(BRIEFS["ecommerce"][0])
    task_ids = {t.id for t in plan.tasks}
    for dep in plan.dependencies:
        assert dep.task_id in task_ids
        assert dep.depends_on in task_ids
        assert dep.task_id != dep.depends_on


# ---------------------------------------------------------------------------
# Mode selection and configuration
# ---------------------------------------------------------------------------


def test_use_fallback_flag(monkeypatch):
    monkeypatch.delenv("AI_USE_FALLBACK", raising=False)
    assert use_fallback() is False
    monkeypatch.setenv("AI_USE_FALLBACK", "1")
    assert use_fallback() is True
    monkeypatch.setenv("AI_USE_FALLBACK", "true")
    assert use_fallback() is True
    monkeypatch.setenv("AI_USE_FALLBACK", "0")
    assert use_fallback() is False


def test_plan_project_uses_fallback_when_enabled(monkeypatch):
    monkeypatch.setenv("AI_USE_FALLBACK", "1")
    plan = plan_project(BRIEFS["todo"][0])
    assert plan == generate_fallback_plan(BRIEFS["todo"][0])


def test_fallback_mode_skips_gemini_entirely(monkeypatch):
    """AI_USE_FALLBACK=1 must never construct the Gemini planner."""

    def boom(*args, **kwargs):
        raise AssertionError("GeminiPlanner must not be constructed in fallback mode")

    import app.services.ai_planner as planner_module

    monkeypatch.setattr(planner_module, "GeminiPlanner", boom)
    monkeypatch.setenv("AI_USE_FALLBACK", "1")
    plan = plan_project(BRIEFS["todo"][0])
    assert plan == generate_fallback_plan(BRIEFS["todo"][0])


def test_gemini_planner_requires_api_key(monkeypatch):
    """Constructing the real planner without a key is a configuration error."""
    monkeypatch.delenv("AI_LLM_API_KEY", raising=False)
    with pytest.raises(AIPlannerConfigurationError):
        GeminiPlanner()


def test_plan_project_auto_falls_back_without_api_key(monkeypatch, caplog):
    """No key + AI_USE_FALLBACK=0 -> Gemini config error -> fallback plan."""
    monkeypatch.delenv("AI_USE_FALLBACK", raising=False)
    monkeypatch.delenv("AI_LLM_API_KEY", raising=False)
    with caplog.at_level(logging.WARNING):
        plan = plan_project(BRIEFS["todo"][0])
    assert plan == generate_fallback_plan(BRIEFS["todo"][0])
    assert "fallback" in caplog.text


def test_plan_project_rejects_empty_brief(monkeypatch):
    monkeypatch.setenv("AI_USE_FALLBACK", "1")
    with pytest.raises(ValueError):
        plan_project("  ")


def test_plan_project_rejects_very_short_brief(monkeypatch):
    monkeypatch.setenv("AI_USE_FALLBACK", "1")
    with pytest.raises(ValueError, match="too short"):
        plan_project("x")


def test_no_api_key_hardcoded():
    """The service must not contain a literal API key."""
    import pathlib

    source = pathlib.Path(__file__).resolve().parents[1] / "backend" / "app" / "services"
    for file in source.glob("*.py"):
        text = file.read_text()
        assert "sk-" not in text, f"found a hardcoded-looking key in {file.name}"
        assert "AIza" not in text, f"found a hardcoded-looking Gemini key in {file.name}"

    planner_source = (source / "ai_planner.py").read_text()
    assert 'os.getenv("AI_LLM_API_KEY")' in planner_source


# ---------------------------------------------------------------------------
# Real planner (mocked Gemini client)
# ---------------------------------------------------------------------------


class FakeGeminiModels:
    def __init__(self, text=None, error=None):
        self.text = text
        self.error = error
        self.last_kwargs = None

    def generate_content(self, **kwargs):
        self.last_kwargs = kwargs
        if self.error is not None:
            raise self.error
        if self.text is None:
            return SimpleNamespace()  # missing `.text` like a malformed response
        return SimpleNamespace(text=self.text)


class FakeGeminiClient:
    def __init__(self, text=None, error=None):
        self.models = FakeGeminiModels(text=text, error=error)


def _planner_with(text, error=None, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setenv("AI_LLM_API_KEY", "test-key-not-real")
    return GeminiPlanner(client=FakeGeminiClient(text=text, error=error))


# A realistic brief that passes the minimum-length guard.
_PLANNER_BRIEF = "Build a todo application for personal task management."


def _valid_plan_json() -> str:
    return json.dumps(
        {
            "project": {"name": "Todo App", "summary": "Simple todo list."},
            "requirements": [{"id": 1, "title": "Manage todos"}],
            "modules": [{"id": 1, "name": "Tasks"}],
            "tasks": [
                {
                    "id": 1,
                    "module_id": 1,
                    "requirement_id": 1,
                    "title": "Add a todo",
                    "priority": "HIGH",
                    "acceptance_criteria": ["Todo is listed."],
                }
            ],
            "dependencies": [],
        }
    )


def test_planner_returns_valid_plan_from_json(monkeypatch):
    planner = _planner_with(_valid_plan_json(), monkeypatch=monkeypatch)
    plan = planner.generate_plan("Build a todo app.")

    assert isinstance(plan, ProjectPlan)
    assert plan.project.name == "Todo App"
    assert plan.tasks[0].title == "Add a todo"
    assert plan.tasks[0].priority.value == "HIGH"


def test_planner_request_shape(monkeypatch):
    planner = _planner_with(_valid_plan_json(), monkeypatch=monkeypatch)
    planner.generate_plan("Build a todo app.")

    kwargs = planner.client.models.last_kwargs
    assert kwargs["model"] == "gemini-3.5-flash"
    assert "Build a todo app." in kwargs["contents"]

    config = kwargs["config"]
    assert config.response_mime_type == "application/json"
    assert config.temperature == 0.2
    assert "Zenera Labs" in config.system_instruction


def test_planner_model_override(monkeypatch):
    monkeypatch.setenv("AI_LLM_MODEL", "custom-model")
    planner = _planner_with(_valid_plan_json(), monkeypatch=monkeypatch)
    planner.generate_plan(_PLANNER_BRIEF)
    assert planner.client.models.last_kwargs["model"] == "custom-model"


def test_planner_rejects_invalid_json(monkeypatch):
    planner = _planner_with("this is not json", monkeypatch=monkeypatch)
    with pytest.raises(InvalidAIOutputError):
        planner.generate_plan(_PLANNER_BRIEF)


def test_planner_rejects_schema_invalid_output(monkeypatch):
    bad = json.dumps({"project": {"summary": "no name"}})
    planner = _planner_with(bad, monkeypatch=monkeypatch)
    with pytest.raises(InvalidAIOutputError):
        planner.generate_plan(_PLANNER_BRIEF)


def test_planner_rejects_self_dependency_in_output(monkeypatch):
    data = json.loads(_valid_plan_json())
    data["dependencies"] = [{"task_id": 1, "depends_on": 1}]
    planner = _planner_with(json.dumps(data), monkeypatch=monkeypatch)
    with pytest.raises(InvalidAIOutputError):
        planner.generate_plan(_PLANNER_BRIEF)


def test_planner_rejects_empty_content(monkeypatch):
    planner = _planner_with("", monkeypatch=monkeypatch)
    with pytest.raises(InvalidAIOutputError):
        planner.generate_plan(_PLANNER_BRIEF)


def test_planner_rejects_malformed_response_structure(monkeypatch):
    monkeypatch.setenv("AI_LLM_API_KEY", "test-key-not-real")
    planner = GeminiPlanner(client=FakeGeminiClient(text=None))
    with pytest.raises(InvalidAIOutputError):
        planner.generate_plan(_PLANNER_BRIEF)


def test_planner_wraps_generic_api_errors(monkeypatch):
    planner = _planner_with(None, error=RuntimeError("connection reset"), monkeypatch=monkeypatch)
    with pytest.raises(AIPlannerError) as excinfo:
        planner.generate_plan(_PLANNER_BRIEF)
    assert "connection reset" in str(excinfo.value)
    assert not isinstance(excinfo.value, InvalidAIOutputError)


def test_planner_rejects_empty_brief(monkeypatch):
    planner = _planner_with(_valid_plan_json(), monkeypatch=monkeypatch)
    with pytest.raises(ValueError):
        planner.generate_plan("  ")


def test_planner_rejects_very_short_brief(monkeypatch):
    planner = _planner_with(_valid_plan_json(), monkeypatch=monkeypatch)
    with pytest.raises(ValueError, match="too short"):
        planner.generate_plan("x")


def test_planner_rejects_invalid_priority_in_output(monkeypatch):
    data = json.loads(_valid_plan_json())
    data["tasks"][0]["priority"] = "URGENT"
    planner = _planner_with(json.dumps(data), monkeypatch=monkeypatch)
    with pytest.raises(InvalidAIOutputError):
        planner.generate_plan(_PLANNER_BRIEF)


def test_planner_rejects_invalid_status_in_output(monkeypatch):
    data = json.loads(_valid_plan_json())
    data["tasks"][0]["status"] = "WHATEVER"
    planner = _planner_with(json.dumps(data), monkeypatch=monkeypatch)
    with pytest.raises(InvalidAIOutputError):
        planner.generate_plan(_PLANNER_BRIEF)


def test_planner_rejects_duplicate_task_ids_in_output(monkeypatch):
    data = json.loads(_valid_plan_json())
    data["tasks"].append(
        {"id": 1, "module_id": 1, "requirement_id": 1, "title": "Duplicate task"}
    )
    planner = _planner_with(json.dumps(data), monkeypatch=monkeypatch)
    with pytest.raises(InvalidAIOutputError):
        planner.generate_plan(_PLANNER_BRIEF)


def test_planner_rejects_dependency_on_unknown_task(monkeypatch):
    data = json.loads(_valid_plan_json())
    data["dependencies"] = [{"task_id": 1, "depends_on": 99}]
    planner = _planner_with(json.dumps(data), monkeypatch=monkeypatch)
    with pytest.raises(InvalidAIOutputError):
        planner.generate_plan(_PLANNER_BRIEF)


def test_planner_parses_generated_status(monkeypatch):
    """A valid status from the model is accepted and preserved."""
    data = json.loads(_valid_plan_json())
    data["tasks"][0]["status"] = "IN_PROGRESS"
    planner = _planner_with(json.dumps(data), monkeypatch=monkeypatch)
    plan = planner.generate_plan(_PLANNER_BRIEF)
    assert plan.tasks[0].status.value == "IN_PROGRESS"


def test_planner_status_defaults_to_todo(monkeypatch):
    """A plan without a status field validates and defaults to TODO."""
    planner = _planner_with(_valid_plan_json(), monkeypatch=monkeypatch)
    plan = planner.generate_plan(_PLANNER_BRIEF)
    assert plan.tasks[0].status.value == "TODO"


# ---------------------------------------------------------------------------
# Provider error wrapping (GeminiPlanner level)
# ---------------------------------------------------------------------------


def _gemini_client_error(code, message):
    from google.genai import errors

    return errors.ClientError(code=code, response_json={"error": {"message": message}})


@pytest.mark.parametrize(
    "error",
    [
        _gemini_client_error(401, "API key not valid."),
        _gemini_client_error(429, "Quota exceeded."),
        _gemini_client_error(403, "Permission denied."),
    ],
    ids=["auth", "quota", "permission"],
)
def test_planner_wraps_http_client_errors(monkeypatch, error):
    planner = _planner_with(None, error=error, monkeypatch=monkeypatch)
    with pytest.raises(AIPlannerError):
        planner.generate_plan(_PLANNER_BRIEF)


def test_planner_wraps_server_errors(monkeypatch):
    from google.genai import errors

    planner = _planner_with(
        None, error=errors.ServerError(code=500, response_json={"error": {}}), monkeypatch=monkeypatch
    )
    with pytest.raises(AIPlannerError):
        planner.generate_plan(_PLANNER_BRIEF)


def test_planner_wraps_timeout_errors(monkeypatch):
    import httpx

    planner = _planner_with(None, error=httpx.ReadTimeout("request timed out"), monkeypatch=monkeypatch)
    with pytest.raises(AIPlannerError) as excinfo:
        planner.generate_plan(_PLANNER_BRIEF)
    assert "timed out" in str(excinfo.value)


def test_planner_wraps_network_errors(monkeypatch):
    import httpx

    planner = _planner_with(None, error=httpx.ConnectError("connection refused"), monkeypatch=monkeypatch)
    with pytest.raises(AIPlannerError):
        planner.generate_plan(_PLANNER_BRIEF)


# ---------------------------------------------------------------------------
# Automatic fallback (plan_project level)
# ---------------------------------------------------------------------------


def _install_failing_planner(monkeypatch, *, text=None, error=None):
    """Point plan_project's GeminiPlanner at a fake client with the given
    text (valid JSON or not) or the given provider error, so the REAL
    GeminiPlanner code path runs and plan_project handles the failure."""
    import app.services.ai_planner as planner_module

    monkeypatch.setenv("AI_LLM_API_KEY", "test-key-not-real")
    real = planner_module.GeminiPlanner
    fake = FakeGeminiClient(text=text, error=error)
    monkeypatch.setattr(planner_module, "GeminiPlanner", lambda **kwargs: real(client=fake))
    return fake


def test_plan_project_uses_gemini_plan_on_success(monkeypatch):
    """Gemini success -> the Gemini plan is used, not the fallback."""
    import app.services.ai_planner as planner_module

    monkeypatch.setenv("AI_LLM_API_KEY", "test-key-not-real")
    real = planner_module.GeminiPlanner
    fake = FakeGeminiClient(text=_valid_plan_json())
    monkeypatch.setattr(planner_module, "GeminiPlanner", lambda **kwargs: real(client=fake))

    plan = plan_project(_PLANNER_BRIEF)
    assert plan.project.name == "Todo App"  # Gemini output, not the fallback's
    assert plan.tasks[0].title == "Add a todo"


def test_plan_project_falls_back_on_auth_failure(monkeypatch, caplog):
    _install_failing_planner(monkeypatch, error=_gemini_client_error(401, "API key not valid."))
    with caplog.at_level(logging.WARNING):
        plan = plan_project(BRIEFS["todo"][0])
    assert plan == generate_fallback_plan(BRIEFS["todo"][0])
    ProjectPlan.model_validate(plan.model_dump())
    assert "fallback" in caplog.text


def test_plan_project_falls_back_on_quota_failure(monkeypatch, caplog):
    _install_failing_planner(monkeypatch, error=_gemini_client_error(429, "Quota exceeded."))
    with caplog.at_level(logging.WARNING):
        plan = plan_project(BRIEFS["todo"][0])
    assert plan == generate_fallback_plan(BRIEFS["todo"][0])
    ProjectPlan.model_validate(plan.model_dump())
    assert "fallback" in caplog.text


def test_plan_project_falls_back_on_timeout(monkeypatch, caplog):
    import httpx

    _install_failing_planner(monkeypatch, error=httpx.ReadTimeout("request timed out"))
    with caplog.at_level(logging.WARNING):
        plan = plan_project(BRIEFS["todo"][0])
    assert plan == generate_fallback_plan(BRIEFS["todo"][0])
    assert "fallback" in caplog.text


def test_plan_project_falls_back_on_network_failure(monkeypatch, caplog):
    import httpx

    _install_failing_planner(monkeypatch, error=httpx.ConnectError("connection refused"))
    with caplog.at_level(logging.WARNING):
        plan = plan_project(BRIEFS["todo"][0])
    assert plan == generate_fallback_plan(BRIEFS["todo"][0])
    assert "fallback" in caplog.text


def test_plan_project_falls_back_on_malformed_json(monkeypatch, caplog):
    _install_failing_planner(monkeypatch, text="this is not json")
    with caplog.at_level(logging.WARNING):
        plan = plan_project(BRIEFS["todo"][0])
    assert plan == generate_fallback_plan(BRIEFS["todo"][0])
    assert "fallback" in caplog.text


def test_plan_project_falls_back_on_invalid_plan(monkeypatch, caplog):
    _install_failing_planner(monkeypatch, text=json.dumps({"project": {"summary": "no name"}}))
    with caplog.at_level(logging.WARNING):
        plan = plan_project(BRIEFS["todo"][0])
    assert plan == generate_fallback_plan(BRIEFS["todo"][0])
    ProjectPlan.model_validate(plan.model_dump())
    assert "fallback" in caplog.text


def test_plan_project_does_not_fallback_on_non_ai_exceptions(monkeypatch):
    """Only AIPlannerError triggers the fallback; unrelated exceptions propagate."""

    class WeirdPlanner:
        def generate_plan(self, brief):
            raise ValueError("something unrelated")

    import app.services.ai_planner as planner_module

    monkeypatch.setattr(planner_module, "GeminiPlanner", lambda **kwargs: WeirdPlanner())
    with pytest.raises(ValueError, match="something unrelated"):
        plan_project(BRIEFS["todo"][0])


# ---------------------------------------------------------------------------
# Prompt quality
# ---------------------------------------------------------------------------


def test_prompt_enforces_strict_json_output():
    from app.services.prompts import PLANNER_SYSTEM_PROMPT, build_planning_prompt

    prompt = build_planning_prompt("Build a todo application.")
    assert "Build a todo application." in prompt
    assert "no markdown" in prompt.lower()
    assert "code fences" in prompt
    assert "single JSON object" in prompt
    assert "JSON object" in PLANNER_SYSTEM_PROMPT
    assert "no prose" in PLANNER_SYSTEM_PROMPT


def test_prompt_contains_planning_quality_rules():
    from app.services.prompts import build_planning_prompt

    prompt = build_planning_prompt("Build a todo application.")
    lower = prompt.lower()

    # Cardinality guidance (3-8, adapted to complexity).
    assert "3-8" in prompt
    assert "major requirements" in prompt
    assert "modules" in prompt
    assert "adapt the plan to the complexity" in lower

    # Scope and duplication.
    assert "do not invent unnecessary requirements" in lower
    assert "duplicate tasks" in prompt

    # Task quality.
    assert "acceptance criteria" in lower
    assert "todo" in lower and "in_progress" in lower
    assert "blocked" in lower and "done" in lower
    assert "high, medium, low" in lower

    # Dependencies and references.
    assert "realistic implementation order" in lower
    assert "never depend on itself" in prompt
    assert "unique integer ids" in prompt
    assert "existing task id" in prompt


def test_prompt_asks_for_realistic_dependency_example():
    from app.services.prompts import build_planning_prompt

    prompt = build_planning_prompt("Build a todo application.")
    assert "Database schema" in prompt
    assert "Authentication API" in prompt
    assert "Authentication UI" in prompt
    assert "Protected dashboard" in prompt
