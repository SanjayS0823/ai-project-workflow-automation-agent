"""Project and plan API routes."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Module, Project, Requirement, Task
from ..schemas import (
    GeneratePlanRequest,
    ProjectCreate,
    ProjectListOut,
    ProjectOut,
    ProjectPlanResponse,
)
from ..services.ai_planner import AIPlannerError, plan_project
from ..services.plan_storage import persist_plan
from .serializers import load_project_with_plan, project_plan_response

router = APIRouter(prefix="/api/projects", tags=["projects"])

# Shown to users when the AI planner fails; never expose internals.
AI_FAILURE_MESSAGE = "Unable to generate the project plan. Please try again."


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> Project:
    """Create a project."""
    project = Project(
        name=payload.name,
        description=payload.description,
        original_brief=payload.original_brief,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=List[ProjectListOut])
def list_projects(db: Session = Depends(get_db)) -> List[ProjectListOut]:
    """List all projects, newest first, with child counts."""
    requirement_counts = (
        select(Requirement.project_id, func.count().label("n"))
        .group_by(Requirement.project_id)
        .subquery()
    )
    module_counts = (
        select(Module.project_id, func.count().label("n"))
        .group_by(Module.project_id)
        .subquery()
    )
    task_counts = (
        select(Task.project_id, func.count().label("n"))
        .group_by(Task.project_id)
        .subquery()
    )
    stmt = (
        select(Project, requirement_counts.c.n, module_counts.c.n, task_counts.c.n)
        .outerjoin(requirement_counts, requirement_counts.c.project_id == Project.id)
        .outerjoin(module_counts, module_counts.c.project_id == Project.id)
        .outerjoin(task_counts, task_counts.c.project_id == Project.id)
        .order_by(Project.created_at.desc(), Project.id.desc())
    )
    rows = db.execute(stmt).all()

    projects: List[ProjectListOut] = []
    for project, requirements_n, modules_n, tasks_n in rows:
        out = ProjectListOut.model_validate(project)
        projects.append(
            out.model_copy(
                update={
                    "requirements_count": requirements_n or 0,
                    "modules_count": modules_n or 0,
                    "tasks_count": tasks_n or 0,
                }
            )
        )
    return projects


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)) -> Project:
    """Get a single project."""
    return _get_project_or_404(db, project_id)


@router.post("/{project_id}/generate-plan", response_model=ProjectPlanResponse)
def generate_project_plan(
    project_id: int, payload: GeneratePlanRequest, db: Session = Depends(get_db)
) -> ProjectPlanResponse:
    """Generate an AI plan for a project and store it.

    Steps: brief -> AI planner -> validation -> store requirements, modules,
    tasks, acceptance criteria, and dependencies -> return the stored plan.
    """
    project = _get_project_or_404(db, project_id)

    try:
        plan = plan_project(payload.brief)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except AIPlannerError:
        raise HTTPException(status_code=502, detail=AI_FAILURE_MESSAGE)

    persist_plan(db, project, plan, original_brief=payload.brief)

    stored = load_project_with_plan(db, project.id)
    return project_plan_response(stored)


@router.get("/{project_id}/plan", response_model=ProjectPlanResponse)
def get_project_plan(project_id: int, db: Session = Depends(get_db)) -> ProjectPlanResponse:
    """Return the complete stored plan for a project."""
    project = load_project_with_plan(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")

    has_plan = bool(project.tasks or project.modules or project.requirements)
    if not has_plan:
        raise HTTPException(
            status_code=404,
            detail="Plan has not been generated for this project yet.",
        )
    return project_plan_response(project)
