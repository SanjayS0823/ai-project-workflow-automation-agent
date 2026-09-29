"""SQLAlchemy ORM models for the AI Project & Workflow Automation Agent.

Phase 2: database layer only. No AI or API logic lives here.

Note: `Optional[...]` / `List[...]` (rather than `X | None` / `list[X]`) are
used so the mapped annotations resolve on Python 3.9.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Project(Base):
    """A planning project created from a natural-language brief."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    original_brief: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    requirements: Mapped[List[Requirement]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    modules: Mapped[List[Module]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    tasks: Mapped[List[Task]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Project id={self.id} name={self.name!r}>"


class Requirement(Base):
    """A requirement extracted from the project brief."""

    __tablename__ = "requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    project: Mapped[Project] = relationship(back_populates="requirements")
    tasks: Mapped[List[Task]] = relationship(back_populates="requirement")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Requirement id={self.id} title={self.title!r}>"


class Module(Base):
    """A functional module grouping tasks within a project."""

    __tablename__ = "modules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship(back_populates="modules")
    tasks: Mapped[List[Task]] = relationship(back_populates="module")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Module id={self.id} name={self.name!r}>"


class Task(Base):
    """A development task / user story with priority and status."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    module_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("modules.id", ondelete="CASCADE"), nullable=True, index=True
    )
    requirement_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="MEDIUM")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="TODO")
    # Set when the user explicitly creates a GitHub issue for this task.
    github_issue_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    project: Mapped[Project] = relationship(back_populates="tasks")
    module: Mapped[Optional[Module]] = relationship(back_populates="tasks")
    requirement: Mapped[Optional[Requirement]] = relationship(back_populates="tasks")
    acceptance_criteria: Mapped[List[AcceptanceCriterion]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )
    # Dependencies this task has (rows where task_id == this task).
    dependencies: Mapped[List[TaskDependency]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        foreign_keys="TaskDependency.task_id",
    )
    # Tasks that depend on this task (rows where depends_on_task_id == this task).
    dependents: Mapped[List[TaskDependency]] = relationship(
        back_populates="depends_on",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys="TaskDependency.depends_on_task_id",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Task id={self.id} title={self.title!r}>"


class AcceptanceCriterion(Base):
    """A single acceptance criterion for a task."""

    __tablename__ = "acceptance_criteria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    criterion: Mapped[str] = mapped_column(Text, nullable=False)

    task: Mapped[Task] = relationship(back_populates="acceptance_criteria")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AcceptanceCriterion id={self.id}>"


class TaskDependency(Base):
    """A dependency edge: task_id depends on depends_on_task_id."""

    __tablename__ = "task_dependencies"
    __table_args__ = (
        CheckConstraint(
            "task_id != depends_on_task_id",
            name="ck_task_no_self_dependency",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    depends_on_task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )

    task: Mapped[Task] = relationship(
        back_populates="dependencies", foreign_keys="TaskDependency.task_id"
    )
    depends_on: Mapped[Task] = relationship(
        back_populates="dependents",
        foreign_keys="TaskDependency.depends_on_task_id",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<TaskDependency id={self.id} "
            f"task_id={self.task_id} depends_on={self.depends_on_task_id}>"
        )
