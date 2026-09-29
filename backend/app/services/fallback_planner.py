"""Deterministic development fallback for the AI planning service.

Used only for local testing when AI_USE_FALLBACK=1 is set. Produces a small,
valid ProjectPlan grounded in the brief via simple keyword matching.

This is intentionally simple and is NOT a substitute for the real AI planner
in production. It exists so the API can be exercised end-to-end without an
LLM API key.
"""

from typing import Dict, List

from ..schemas import (
    PlanDependency,
    PlanModule,
    PlanProject,
    PlanRequirement,
    PlanTask,
    ProjectPlan,
)

# Each entry: keywords matched against the lowercased brief, plus a module, a
# requirement, and the tasks (title, priority, acceptance criteria) that belong
# to it.
_FALLBACK_CATALOG: List[Dict] = [
    {
        "keywords": ["regist", "login", "log in", "sign", "account", "auth", "profile"],
        "module": ("Accounts", "User registration, login, and profile management."),
        "requirement": ("User accounts", "Users can register, log in, and manage their profile."),
        "tasks": [
            (
                "Implement user registration",
                "HIGH",
                ["Users can register with an email and password.", "Registration errors are shown clearly."],
            ),
            (
                "Implement login and logout",
                "HIGH",
                ["Registered users can log in and out.", "Sessions persist across page reloads."],
            ),
        ],
    },
    {
        "keywords": ["browse", "search", "product", "catalog", "listing", "filter"],
        "module": ("Catalog", "Product browsing, search, and filtering."),
        "requirement": ("Product catalog", "Users can browse and search the available products."),
        "tasks": [
            (
                "Build product listing page",
                "HIGH",
                ["Products are listed with name and price.", "Listings can be filtered by category."],
            ),
            (
                "Add product search",
                "MEDIUM",
                ["Search returns matching products.", "Empty results show a friendly message."],
            ),
        ],
    },
    {
        "keywords": ["cart", "checkout", "order", "payment", "purchase", "buy"],
        "module": ("Cart & Checkout", "Cart management and order placement."),
        "requirement": ("Cart and orders", "Users can add products to a cart and place orders."),
        "tasks": [
            (
                "Build shopping cart",
                "HIGH",
                ["Users can add and remove items.", "Cart totals update correctly."],
            ),
            (
                "Implement checkout and order placement",
                "HIGH",
                ["Users can place an order with their details.", "An order confirmation is shown."],
            ),
        ],
    },
    {
        "keywords": ["appointment", "doctor", "slot", "schedule", "booking", "book"],
        "module": ("Appointments", "Doctor search, slot viewing, and booking."),
        "requirement": ("Appointments", "Patients can search for doctors, view slots, and book appointments."),
        "tasks": [
            (
                "Search for doctors",
                "HIGH",
                ["Patients can search doctors by specialty.", "Results show name and specialty."],
            ),
            (
                "View available slots",
                "MEDIUM",
                ["Available slots are shown for a selected doctor.", "Booked slots are not offered."],
            ),
            (
                "Book an appointment",
                "HIGH",
                ["Patients can book an available slot.", "Booking is confirmed with a reference."],
            ),
        ],
    },
    {
        "keywords": ["todo", "to-do", "task list", "reminder"],
        "module": ("Tasks", "Todo item management."),
        "requirement": ("Todo list", "Users can create, view, complete, and remove todos."),
        "tasks": [
            (
                "Create and list todos",
                "HIGH",
                ["Users can add todos and see them listed.", "Todos persist after refresh."],
            ),
            (
                "Mark todos complete and delete",
                "MEDIUM",
                ["Users can mark todos done.", "Users can delete todos."],
            ),
        ],
    },
]

# Used when no catalog entry matches the brief.
_GENERIC_MODULE = {
    "module": ("Core Application", "Core application foundation."),
    "requirement": ("Core functionality", "The application implements the functionality described in the brief."),
    "tasks": [
        (
            "Define project scope and requirements",
            "HIGH",
            ["Project scope is documented from the brief."],
        ),
        (
            "Set up application foundation",
            "HIGH",
            ["Application scaffolding builds and runs."],
        ),
        (
            "Implement core features from the brief",
            "HIGH",
            ["Core functionality matches the brief."],
        ),
    ],
}


def _project_name(brief: str) -> str:
    cleaned = " ".join(brief.split())
    for end in (".", "!", "?"):
        idx = cleaned.find(end)
        if 0 < idx <= 80:
            cleaned = cleaned[: idx + 1]
            break
    return cleaned[:80].strip() or "Project Plan"


def _summary(brief: str) -> str:
    return " ".join(brief.split())[:200] or "No brief provided."


def generate_fallback_plan(brief: str) -> ProjectPlan:
    """Generate a deterministic ProjectPlan for the given brief.

    Raises ValueError if the brief is empty (after stripping).
    """
    brief = (brief or "").strip()
    if not brief:
        raise ValueError("Project brief must not be empty.")

    text = brief.lower()
    selected = [
        entry for entry in _FALLBACK_CATALOG if any(k in text for k in entry["keywords"])
    ]
    if not selected:
        selected = [_GENERIC_MODULE]

    requirements: List[PlanRequirement] = []
    modules: List[PlanModule] = []
    tasks: List[PlanTask] = []
    dependencies: List[PlanDependency] = []

    next_task_id = 1
    for index, entry in enumerate(selected, start=1):
        module = PlanModule(id=index, name=entry["module"][0], description=entry["module"][1])
        requirement = PlanRequirement(
            id=index, title=entry["requirement"][0], description=entry["requirement"][1]
        )
        modules.append(module)
        requirements.append(requirement)

        previous_in_module = None
        for title, priority, criteria in entry["tasks"]:
            task_id = next_task_id
            tasks.append(
                PlanTask(
                    id=task_id,
                    module_id=module.id,
                    requirement_id=requirement.id,
                    title=title,
                    priority=priority,
                    acceptance_criteria=criteria,
                )
            )
            if previous_in_module is not None:
                dependencies.append(
                    PlanDependency(task_id=task_id, depends_on=previous_in_module)
                )
            previous_in_module = task_id
            next_task_id += 1

    return ProjectPlan(
        project=PlanProject(name=_project_name(brief), summary=_summary(brief)),
        requirements=requirements,
        modules=modules,
        tasks=tasks,
        dependencies=dependencies,
    )
