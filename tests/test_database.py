"""Phase 2 tests: database models, relationships, cascades, and integrity."""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import (
    AcceptanceCriterion,
    Module,
    Project,
    Requirement,
    Task,
    TaskDependency,
)


# ---------------------------------------------------------------------------
# Project CRUD
# ---------------------------------------------------------------------------


def test_create_and_retrieve_project(db_session):
    project = Project(
        name="E-commerce Platform",
        description="Online store",
        original_brief="Build an e-commerce application.",
    )
    db_session.add(project)
    db_session.commit()

    fetched = db_session.get(Project, project.id)
    assert fetched.name == "E-commerce Platform"
    assert fetched.description == "Online store"
    assert fetched.original_brief == "Build an e-commerce application."
    assert fetched.created_at is not None
    assert fetched.updated_at is not None


def test_project_name_is_required(db_session):
    db_session.add(Project(name=None))  # type: ignore[arg-type]
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_update_project_touches_updated_at(db_session):
    project = Project(name="Original")
    db_session.add(project)
    db_session.commit()

    created_at = project.created_at
    project.name = "Renamed"
    db_session.commit()

    assert project.created_at == created_at
    assert project.updated_at >= created_at


# ---------------------------------------------------------------------------
# Child record CRUD and relationships
# ---------------------------------------------------------------------------


def test_create_and_retrieve_requirement(db_session):
    project = Project(name="Hospital System")
    requirement = Requirement(
        project=project,
        title="Patient registration",
        description="Patients can register with their details.",
    )
    db_session.add(project)
    db_session.commit()

    fetched = db_session.get(Requirement, requirement.id)
    assert fetched.title == "Patient registration"
    assert fetched.description == "Patients can register with their details."
    assert fetched.created_at is not None
    assert fetched.project.name == "Hospital System"


def test_project_to_children_relationships(db_session):
    project = Project(name="E-commerce")
    module = Module(project=project, name="Auth", description="Login and signup")
    requirement = Requirement(
        project=project, title="User accounts", description="Users can register and log in."
    )
    task = Task(
        project=project,
        module=module,
        requirement=requirement,
        title="Build registration form",
        description="Create the signup UI and validation.",
    )
    db_session.add(project)
    db_session.commit()

    fetched = db_session.get(Project, project.id)
    assert len(fetched.modules) == 1
    assert len(fetched.requirements) == 1
    assert len(fetched.tasks) == 1

    task = fetched.tasks[0]
    assert task.module.name == "Auth"
    assert task.requirement.title == "User accounts"
    assert task.priority == "MEDIUM"
    assert task.status == "TODO"
    assert task.created_at is not None
    assert task.updated_at is not None


def test_module_task_count_via_relationship(db_session):
    project = Project(name="E-commerce")
    module = Module(project=project, name="Cart")
    db_session.add_all([project, module])
    db_session.flush()

    for i in range(3):
        db_session.add(Task(project=project, module=module, title=f"Task {i}"))
    db_session.commit()

    fetched_module = db_session.get(Module, module.id)
    assert len(fetched_module.tasks) == 3


# ---------------------------------------------------------------------------
# Acceptance criteria and dependencies
# ---------------------------------------------------------------------------


def test_task_acceptance_criteria_relationship(db_session):
    project = Project(name="Todo App")
    task = Task(project=project, title="Add a todo", description="Users can add todos.")
    db_session.add_all([project, task])
    db_session.flush()

    db_session.add_all(
        [
            AcceptanceCriterion(task=task, criterion="Todo appears in the list."),
            AcceptanceCriterion(task=task, criterion="Todo is saved after refresh."),
        ]
    )
    db_session.commit()

    fetched = db_session.get(Task, task.id)
    assert [c.criterion for c in fetched.acceptance_criteria] == [
        "Todo appears in the list.",
        "Todo is saved after refresh.",
    ]


def test_task_dependency_relationship_both_directions(db_session):
    project = Project(name="E-commerce")
    setup_task = Task(project=project, title="Set up database")
    cart_task = Task(project=project, title="Build cart")
    db_session.add_all([project, setup_task, cart_task])
    db_session.flush()

    db_session.add(TaskDependency(task=cart_task, depends_on=setup_task))
    db_session.commit()

    cart = db_session.get(Task, cart_task.id)
    setup = db_session.get(Task, setup_task.id)
    assert len(cart.dependencies) == 1
    assert cart.dependencies[0].depends_on.id == setup.id
    assert len(setup.dependents) == 1
    assert setup.dependents[0].task.id == cart.id


# ---------------------------------------------------------------------------
# Integrity rules
# ---------------------------------------------------------------------------


def test_self_dependency_is_rejected(db_session):
    project = Project(name="Todo App")
    task = Task(project=project, title="Do the thing")
    db_session.add_all([project, task])
    db_session.commit()

    db_session.add(TaskDependency(task=task, depends_on=task))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_duplicate_dependency_is_allowed(db_session):
    """Two tasks may only be linked once per direction, but duplicates are a
    planning concern, not a schema violation; this guards the guard."""
    project = Project(name="Todo App")
    a = Task(project=project, title="A")
    b = Task(project=project, title="B")
    db_session.add_all([project, a, b])
    db_session.flush()

    db_session.add_all([TaskDependency(task=b, depends_on=a), TaskDependency(task=b, depends_on=a)])
    db_session.commit()

    fetched = db_session.get(Task, b.id)
    assert len(fetched.dependencies) == 2


def test_dependency_on_missing_task_is_rejected(db_session):
    project = Project(name="Todo App")
    task = Task(project=project, title="Task")
    db_session.add_all([project, task])
    db_session.commit()

    db_session.add(TaskDependency(task_id=task.id, depends_on_task_id=9999))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_task_requires_project(db_session):
    db_session.add(Task(title="Orphan task"))
    with pytest.raises(IntegrityError):
        db_session.commit()


# ---------------------------------------------------------------------------
# Cascades
# ---------------------------------------------------------------------------


def test_delete_task_cascades_criteria_and_dependencies(db_session):
    project = Project(name="E-commerce")
    setup_task = Task(project=project, title="Setup DB")
    cart_task = Task(project=project, title="Cart")
    db_session.add_all([project, setup_task, cart_task])
    db_session.flush()
    db_session.add(AcceptanceCriterion(task=cart_task, criterion="Works."))
    db_session.add(TaskDependency(task=cart_task, depends_on=setup_task))
    db_session.commit()

    db_session.delete(cart_task)
    db_session.commit()

    assert db_session.get(Task, cart_task.id) is None
    assert db_session.query(AcceptanceCriterion).count() == 0
    assert db_session.query(TaskDependency).count() == 0


def test_delete_depended_on_task_removes_dependency_rows(db_session):
    project = Project(name="E-commerce")
    setup_task = Task(project=project, title="Setup DB")
    cart_task = Task(project=project, title="Cart")
    db_session.add_all([project, setup_task, cart_task])
    db_session.flush()
    db_session.add(TaskDependency(task=cart_task, depends_on=setup_task))
    db_session.commit()

    db_session.delete(setup_task)
    db_session.commit()

    assert db_session.get(Task, setup_task.id) is None
    assert db_session.query(TaskDependency).count() == 0


def test_delete_project_cascades_everything(db_session):
    project = Project(name="E-commerce")
    module = Module(project=project, name="Auth")
    requirement = Requirement(project=project, title="Accounts")
    task_a = Task(project=project, module=module, requirement=requirement, title="A")
    task_b = Task(project=project, title="B")
    db_session.add_all([project, module, requirement, task_a, task_b])
    db_session.flush()
    db_session.add(AcceptanceCriterion(task=task_a, criterion="Done."))
    db_session.add(TaskDependency(task=task_b, depends_on=task_a))
    db_session.commit()

    db_session.delete(project)
    db_session.commit()

    assert db_session.query(Project).count() == 0
    assert db_session.query(Module).count() == 0
    assert db_session.query(Requirement).count() == 0
    assert db_session.query(Task).count() == 0
    assert db_session.query(AcceptanceCriterion).count() == 0
    assert db_session.query(TaskDependency).count() == 0


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def test_init_db_creates_tables(tmp_path, monkeypatch):
    import sqlite3

    from sqlalchemy import create_engine

    from app import database

    db_path = tmp_path / "init.db"
    engine = create_engine(f"sqlite:///{db_path}")
    monkeypatch.setattr(database, "engine", engine)
    database.init_db()

    conn = sqlite3.connect(db_path)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    conn.close()
    assert {
        "projects",
        "requirements",
        "modules",
        "tasks",
        "acceptance_criteria",
        "task_dependencies",
    }.issubset(tables)

    deps_table = database.Base.metadata.tables["task_dependencies"]
    constraint_names = {c.name for c in deps_table.constraints}
    assert "ck_task_no_self_dependency" in constraint_names


def test_timestamps_are_datetimes(db_session):
    project = Project(name="Timestamps")
    db_session.add(project)
    db_session.commit()
    assert isinstance(project.created_at, datetime)
    assert isinstance(project.updated_at, datetime)
