"""Serialization helpers: ORM rows -> API response schemas."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import Module, Project, Task
from ..schemas import (
    CriterionOut,
    PlanDependencyOut,
    PlanModuleOut,
    PlanRequirementOut,
    ProjectOut,
    ProjectPlanResponse,
    TaskOut,
)


def task_to_out(task: Task) -> TaskOut:
    """Serialize a task (with criteria and dependencies loaded) for the API."""
    return TaskOut(
        id=task.id,
        project_id=task.project_id,
        module_id=task.module_id,
        requirement_id=task.requirement_id,
        title=task.title,
        description=task.description,
        priority=task.priority,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at,
        module_name=task.module.name if task.module else "",
        requirement_title=task.requirement.title if task.requirement else "",
        acceptance_criteria=[
            CriterionOut(id=c.id, criterion=c.criterion)
            for c in task.acceptance_criteria
        ],
        dependencies=[d.depends_on_task_id for d in task.dependencies],
        github_issue_url=task.github_issue_url,
    )


def load_project_with_plan(db: Session, project_id: int) -> Optional[Project]:
    """Load a project together with its plan rows (eagerly)."""
    stmt = (
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.requirements),
            selectinload(Project.modules).selectinload(Module.tasks),
            selectinload(Project.tasks).selectinload(Task.acceptance_criteria),
            selectinload(Project.tasks).selectinload(Task.dependencies),
        )
    )
    return db.execute(stmt).scalar_one_or_none()


def project_plan_response(project: Project) -> ProjectPlanResponse:
    """Build the full stored-plan response for a project."""
    tasks = sorted(project.tasks, key=lambda t: t.id)
    modules = sorted(project.modules, key=lambda m: m.id)
    return ProjectPlanResponse(
        project=ProjectOut.model_validate(project),
        requirements=[
            PlanRequirementOut(id=r.id, title=r.title, description=r.description or "")
            for r in sorted(project.requirements, key=lambda r: r.id)
        ],
        modules=[
            PlanModuleOut(
                id=m.id,
                name=m.name,
                description=m.description or "",
                task_count=len(m.tasks),
            )
            for m in modules
        ],
        tasks=[task_to_out(t) for t in tasks],
        dependencies=[
            PlanDependencyOut(task_id=d.task_id, depends_on_task_id=d.depends_on_task_id)
            for t in tasks
            for d in sorted(t.dependencies, key=lambda d: d.id)
        ],
    )
