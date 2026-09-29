"""Persisting validated ProjectPlan data into the database.

The plan uses ids local to the plan; this module remaps them to database row
ids. Regenerating a plan replaces the previously stored plan rows.
"""

from sqlalchemy.orm import Session

from ..models import (
    AcceptanceCriterion,
    Module,
    Project,
    Requirement,
    Task,
    TaskDependency,
)
from ..schemas import ProjectPlan


def clear_project_plan(db: Session, project_id: int) -> None:
    """Remove any previously stored plan rows for a project.

    Deletion order matters: tasks first (their FK cascades clean up acceptance
    criteria and dependency edges), then modules, then requirements.
    """
    db.query(Task).filter(Task.project_id == project_id).delete(
        synchronize_session=False
    )
    db.query(Module).filter(Module.project_id == project_id).delete(
        synchronize_session=False
    )
    db.query(Requirement).filter(Requirement.project_id == project_id).delete(
        synchronize_session=False
    )
    db.expire_all()


def persist_plan(
    db: Session, project: Project, plan: ProjectPlan, original_brief: str = None
) -> Project:
    """Store a validated plan under an existing project.

    Replaces any prior plan for the project. Optionally records the brief the
    plan was generated from. Returns the updated project.
    """
    clear_project_plan(db, project.id)

    if original_brief is not None:
        project.original_brief = original_brief

    requirement_ids = {}
    for r in plan.requirements:
        requirement = Requirement(
            project=project,
            title=r.title,
            description=r.description or None,
        )
        db.add(requirement)
        db.flush()
        requirement_ids[r.id] = requirement.id

    module_ids = {}
    for m in plan.modules:
        module = Module(
            project=project,
            name=m.name,
            description=m.description or None,
        )
        db.add(module)
        db.flush()
        module_ids[m.id] = module.id

    task_ids = {}
    for t in plan.tasks:
        task = Task(
            project=project,
            module_id=module_ids.get(t.module_id),
            requirement_id=requirement_ids.get(t.requirement_id),
            title=t.title,
            description=t.description or None,
            priority=t.priority.value,
            status=t.status.value,
        )
        db.add(task)
        db.flush()
        task_ids[t.id] = task.id
        for criterion in t.acceptance_criteria:
            db.add(AcceptanceCriterion(task=task, criterion=criterion))

    for d in plan.dependencies:
        db.add(
            TaskDependency(
                task_id=task_ids[d.task_id],
                depends_on_task_id=task_ids[d.depends_on],
            )
        )

    if plan.project.summary:
        project.description = plan.project.summary

    db.commit()
    db.refresh(project)
    return project
