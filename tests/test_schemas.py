"""Phase 3 tests: Pydantic schema validation for the project plan."""

import pytest
from pydantic import ValidationError

from app.schemas import PlanDependency, PlanTask, Priority, ProjectPlan, TaskStatus


def build_valid_plan() -> dict:
    """A complete, valid plan in the documented ProjectPlan shape."""
    return {
        "project": {
            "name": "E-commerce Platform",
            "summary": "An online store with accounts, catalog, and checkout.",
        },
        "requirements": [
            {"id": 1, "title": "User registration", "description": "Users can create accounts."},
            {"id": 2, "title": "Product catalog", "description": "Products are listed and searchable."},
            {"id": 3, "title": "Shopping cart", "description": "Users can add items to a cart."},
        ],
        "modules": [
            {"id": 1, "name": "Accounts", "description": "Authentication and profiles."},
            {"id": 2, "name": "Catalog", "description": "Product browsing and search."},
            {"id": 3, "name": "Cart & Checkout", "description": "Cart and order placement."},
        ],
        "tasks": [
            {
                "id": 1,
                "module_id": 1,
                "requirement_id": 1,
                "title": "Build registration form",
                "description": "Create signup UI with validation.",
                "priority": "HIGH",
                "acceptance_criteria": [
                    "A user can register with email and password.",
                    "Errors are shown for invalid input.",
                ],
            },
            {
                "id": 2,
                "module_id": 1,
                "requirement_id": 1,
                "title": "Add login and sessions",
                "description": "Users can log in and stay signed in.",
                "priority": "HIGH",
            },
            {
                "id": 3,
                "module_id": 2,
                "requirement_id": 2,
                "title": "Product listing page",
                "description": "Show all products with filters.",
                "priority": "MEDIUM",
            },
            {
                "id": 4,
                "module_id": 3,
                "requirement_id": 3,
                "title": "Cart and checkout flow",
                "description": "Add items, review cart, place order.",
                "priority": "HIGH",
            },
        ],
        "dependencies": [
            {"task_id": 2, "depends_on": 1},
            {"task_id": 4, "depends_on": 3},
            {"task_id": 4, "depends_on": 2},
        ],
    }


# ---------------------------------------------------------------------------
# Valid data
# ---------------------------------------------------------------------------


def test_valid_plan_passes():
    plan = ProjectPlan.model_validate(build_valid_plan())
    assert plan.project.name == "E-commerce Platform"
    assert plan.project.summary.startswith("An online store")
    assert len(plan.requirements) == 3
    assert len(plan.modules) == 3
    assert len(plan.tasks) == 4
    assert len(plan.dependencies) == 3
    assert plan.tasks[0].priority == Priority.HIGH
    assert plan.tasks[0].acceptance_criteria == [
        "A user can register with email and password.",
        "Errors are shown for invalid input.",
    ]


def test_spec_example_shape_with_values():
    """The documented ProjectPlan shape validates when populated."""
    data = {
        "project": {"name": "Hospital Appointment System", "summary": "Book doctor appointments."},
        "requirements": [{"id": 1, "title": "Patient registration"}],
        "modules": [{"id": 1, "name": "Appointments"}],
        "tasks": [
            {
                "id": 1,
                "module_id": 1,
                "requirement_id": 1,
                "title": "Search for doctors",
                "description": "Patients can search doctors by specialty.",
                "priority": "HIGH",
                "acceptance_criteria": ["Results show doctor name and specialty."],
            }
        ],
        "dependencies": [],
    }
    plan = ProjectPlan.model_validate(data)
    assert plan.project.name == "Hospital Appointment System"


def test_defaults_applied():
    task = PlanTask(id=7, title="A task")
    assert task.priority == Priority.MEDIUM
    assert task.description == ""
    assert task.acceptance_criteria == []
    assert task.module_id is None
    assert task.requirement_id is None

    plan = ProjectPlan.model_validate(
        {"project": {"name": "Todo App"}, "requirements": [], "modules": [], "tasks": [], "dependencies": []}
    )
    assert plan.project.summary == ""
    assert plan.requirements == []


def test_dependency_model_roundtrip():
    dep = PlanDependency(task_id=2, depends_on=1)
    assert dep.model_dump() == {"task_id": 2, "depends_on": 1}


# ---------------------------------------------------------------------------
# Required fields
# ---------------------------------------------------------------------------


def test_missing_project_name_rejected():
    data = build_valid_plan()
    del data["project"]["name"]
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


def test_empty_project_name_rejected():
    data = build_valid_plan()
    data["project"]["name"] = ""
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


def test_missing_task_title_rejected():
    data = build_valid_plan()
    del data["tasks"][0]["title"]
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


def test_missing_project_object_rejected():
    data = build_valid_plan()
    del data["project"]
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


def test_missing_task_id_rejected():
    data = build_valid_plan()
    del data["tasks"][0]["id"]
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


# ---------------------------------------------------------------------------
# Priority values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("priority", ["HIGH", "MEDIUM", "LOW"])
def test_valid_priorities_accepted(priority):
    data = build_valid_plan()
    data["tasks"][0]["priority"] = priority
    plan = ProjectPlan.model_validate(data)
    assert plan.tasks[0].priority.value == priority


@pytest.mark.parametrize("priority", ["URGENT", "high", "medium", "High", "CRITICAL", ""])
def test_invalid_priorities_rejected(priority):
    data = build_valid_plan()
    data["tasks"][0]["priority"] = priority
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


# ---------------------------------------------------------------------------
# Status values
# ---------------------------------------------------------------------------


def test_task_status_defaults_to_todo():
    task = PlanTask(id=7, title="A task")
    assert task.status == TaskStatus.TODO


@pytest.mark.parametrize("status", ["TODO", "IN_PROGRESS", "BLOCKED", "DONE"])
def test_valid_statuses_accepted(status):
    data = build_valid_plan()
    data["tasks"][0]["status"] = status
    plan = ProjectPlan.model_validate(data)
    assert plan.tasks[0].status.value == status


@pytest.mark.parametrize("status", ["WHATEVER", "done", "in_progress", "TO DO", ""])
def test_invalid_statuses_rejected(status):
    data = build_valid_plan()
    data["tasks"][0]["status"] = status
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


def test_non_integer_task_id_rejected():
    data = build_valid_plan()
    data["tasks"][0]["id"] = "abc"
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


def test_non_string_title_rejected():
    data = build_valid_plan()
    data["tasks"][0]["title"] = 123
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


def test_non_string_acceptance_criteria_rejected():
    data = build_valid_plan()
    data["tasks"][0]["acceptance_criteria"] = ["ok", 42]
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


def test_string_project_name_rejected():
    data = build_valid_plan()
    data["project"] = "not an object"
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


def test_non_integer_dependency_task_id_rejected():
    data = build_valid_plan()
    data["dependencies"][0]["task_id"] = "x"
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


# ---------------------------------------------------------------------------
# Cross-field references
# ---------------------------------------------------------------------------


def test_task_references_unknown_module_rejected():
    data = build_valid_plan()
    data["tasks"][0]["module_id"] = 99
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


def test_task_references_unknown_requirement_rejected():
    data = build_valid_plan()
    data["tasks"][0]["requirement_id"] = 99
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


def test_dependency_references_unknown_task_rejected():
    data = build_valid_plan()
    data["dependencies"].append({"task_id": 404, "depends_on": 1})
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


def test_dependency_references_unknown_depends_on_rejected():
    data = build_valid_plan()
    data["dependencies"].append({"task_id": 2, "depends_on": 404})
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


def test_self_dependency_rejected():
    data = build_valid_plan()
    data["dependencies"].append({"task_id": 2, "depends_on": 2})
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


def test_duplicate_task_ids_rejected():
    data = build_valid_plan()
    data["tasks"][1]["id"] = data["tasks"][0]["id"]
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


def test_duplicate_module_ids_rejected():
    data = build_valid_plan()
    data["modules"][1]["id"] = data["modules"][0]["id"]
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)


def test_duplicate_requirement_ids_rejected():
    data = build_valid_plan()
    data["requirements"][1]["id"] = data["requirements"][0]["id"]
    with pytest.raises(ValidationError):
        ProjectPlan.model_validate(data)
