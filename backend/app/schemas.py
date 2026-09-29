"""Pydantic schemas for the structured project plan.

These schemas describe the AI-generated plan (the JSON contract between the AI
planner, the API, and the frontend). IDs inside a plan are local to that plan;
they are remapped to database row ids when the plan is persisted (Phase 5).

Phase 3: schemas and validation only. No AI or API logic lives here.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Priority(str, Enum):
    """Task priority values accepted across the application."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TaskStatus(str, Enum):
    """Task status values stored in the database."""

    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    DONE = "DONE"


class PlanProject(BaseModel):
    """Project-level information produced by the planner."""

    name: str = Field(min_length=1, description="Project name.")
    summary: str = Field(default="", description="Short project summary.")


class PlanRequirement(BaseModel):
    """A requirement extracted from the project brief."""

    id: int
    title: str = Field(min_length=1)
    description: str = ""


class PlanModule(BaseModel):
    """A functional module grouping tasks within the project."""

    id: int
    name: str = Field(min_length=1)
    description: str = ""


class PlanTask(BaseModel):
    """A development task / user story in the generated plan."""

    id: int
    module_id: Optional[int] = Field(default=None)
    requirement_id: Optional[int] = Field(default=None)
    title: str = Field(min_length=1)
    description: str = ""
    priority: Priority = Priority.MEDIUM
    status: TaskStatus = TaskStatus.TODO
    acceptance_criteria: List[str] = Field(default_factory=list)


class PlanDependency(BaseModel):
    """A dependency edge: task_id depends on depends_on."""

    task_id: int
    depends_on: int


class ProjectPlan(BaseModel):
    """The complete structured plan produced by the AI planner.

    Shape::

        {
          "project": {"name": "", "summary": ""},
          "requirements": [],
          "modules": [],
          "tasks": [],
          "dependencies": []
        }
    """

    project: PlanProject
    requirements: List[PlanRequirement] = Field(default_factory=list)
    modules: List[PlanModule] = Field(default_factory=list)
    tasks: List[PlanTask] = Field(default_factory=list)
    dependencies: List[PlanDependency] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "ProjectPlan":
        """Reject plans whose internal references do not resolve.

        Enforces:
        - unique task/module/requirement ids
        - module_id / requirement_id on tasks exist in the plan
        - every dependency references existing tasks
        - no task depends on itself
        """
        task_ids = {t.id for t in self.tasks}
        if len(task_ids) != len(self.tasks):
            raise ValueError("Task ids must be unique within the plan.")

        module_ids = {m.id for m in self.modules}
        if len(module_ids) != len(self.modules):
            raise ValueError("Module ids must be unique within the plan.")

        requirement_ids = {r.id for r in self.requirements}
        if len(requirement_ids) != len(self.requirements):
            raise ValueError("Requirement ids must be unique within the plan.")

        for task in self.tasks:
            if task.module_id is not None and task.module_id not in module_ids:
                raise ValueError(
                    f"Task {task.id} references unknown module {task.module_id}."
                )
            if task.requirement_id is not None and task.requirement_id not in requirement_ids:
                raise ValueError(
                    f"Task {task.id} references unknown requirement {task.requirement_id}."
                )

        for dependency in self.dependencies:
            if dependency.task_id not in task_ids:
                raise ValueError(
                    f"Dependency references unknown task {dependency.task_id}."
                )
            if dependency.depends_on not in task_ids:
                raise ValueError(
                    f"Dependency references unknown task {dependency.depends_on}."
                )
            if dependency.task_id == dependency.depends_on:
                raise ValueError(
                    f"Task {dependency.task_id} cannot depend on itself."
                )

        return self


# ---------------------------------------------------------------------------
# API request/response schemas
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    """Payload for creating a project."""

    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    original_brief: Optional[str] = None


class ProjectOut(BaseModel):
    """Project as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    original_brief: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ProjectListOut(ProjectOut):
    """Project row in the list endpoint, with child counts."""

    requirements_count: int = 0
    modules_count: int = 0
    tasks_count: int = 0


class GeneratePlanRequest(BaseModel):
    """Payload for generating an AI plan for a project."""

    brief: str = Field(min_length=10, max_length=20000)


class TaskUpdate(BaseModel):
    """Payload for updating a task. Only provided fields are changed."""

    title: Optional[str] = Field(default=None, min_length=1, max_length=300)
    description: Optional[str] = None
    priority: Optional[Priority] = None
    status: Optional[TaskStatus] = None
    acceptance_criteria: Optional[List[str]] = None


class CriterionOut(BaseModel):
    """A stored acceptance criterion."""

    id: int
    criterion: str


class TaskOut(BaseModel):
    """Task as returned by the API."""

    id: int
    project_id: int
    module_id: Optional[int] = None
    requirement_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    priority: str
    status: str
    created_at: datetime
    updated_at: datetime
    module_name: str = ""
    requirement_title: str = ""
    acceptance_criteria: List[CriterionOut] = Field(default_factory=list)
    dependencies: List[int] = Field(default_factory=list)
    github_issue_url: Optional[str] = None


class PlanRequirementOut(BaseModel):
    """Requirement in the stored-plan response."""

    id: int
    title: str
    description: str = ""


class PlanModuleOut(BaseModel):
    """Module in the stored-plan response."""

    id: int
    name: str
    description: str = ""
    task_count: int = 0


class PlanDependencyOut(BaseModel):
    """Dependency edge in the stored-plan response."""

    task_id: int
    depends_on_task_id: int


class ProjectPlanResponse(BaseModel):
    """The complete stored plan for a project, as returned by the API."""

    project: ProjectOut
    requirements: List[PlanRequirementOut] = Field(default_factory=list)
    modules: List[PlanModuleOut] = Field(default_factory=list)
    tasks: List[TaskOut] = Field(default_factory=list)
    dependencies: List[PlanDependencyOut] = Field(default_factory=list)
