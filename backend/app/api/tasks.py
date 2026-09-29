"""Task API routes."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AcceptanceCriterion, Task
from ..schemas import TaskOut, TaskUpdate
from ..services.github_integration import (
    GitHubIntegrationError,
    GitHubNotConfiguredError,
    create_issue_for_task,
)
from .serializers import task_to_out

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.put("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int, payload: TaskUpdate, db: Session = Depends(get_db)
) -> TaskOut:
    """Update a task. Only provided fields are changed."""
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    if payload.title is not None:
        task.title = payload.title
    if payload.description is not None:
        task.description = payload.description
    if payload.priority is not None:
        task.priority = payload.priority.value
    if payload.status is not None:
        task.status = payload.status.value
    if payload.acceptance_criteria is not None:
        task.acceptance_criteria.clear()
        for criterion in payload.acceptance_criteria:
            task.acceptance_criteria.append(AcceptanceCriterion(criterion=criterion))

    db.commit()
    db.refresh(task)
    return task_to_out(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db)) -> Response:
    """Delete a task. Its acceptance criteria and dependency edges are removed."""
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    db.delete(task)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{task_id}/github-issue", response_model=TaskOut)
def create_task_github_issue(task_id: int, db: Session = Depends(get_db)) -> TaskOut:
    """Create a GitHub issue for a task.

    Explicitly triggered by the user from the task review page — never
    automatic. Idempotent: tasks that already have an issue URL are returned
    unchanged.
    """
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found.")

    try:
        issue_url = create_issue_for_task(task)
    except GitHubNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except GitHubIntegrationError:
        raise HTTPException(
            status_code=502,
            detail="Unable to create the GitHub issue. Please try again.",
        )

    task.github_issue_url = issue_url
    db.commit()
    db.refresh(task)
    return task_to_out(task)
