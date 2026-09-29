"""Prompt templates for the AI planning service.

The planner is a *software project planning assistant*: it converts a
natural-language brief into a complete, validated, implementation-oriented
plan. Output is strictly a single JSON object matching the ProjectPlan schema
(see schemas.py) — no prose, no markdown, no code fences.
"""

PLANNER_SYSTEM_PROMPT = (
    "You are a senior software project planning assistant at Zenera Labs. "
    "You convert natural-language project briefs into complete, structured, "
    "implementation-ready project plans. Stay strictly grounded in the brief: "
    "include only requirements that are explicit or reasonable implications of "
    "it, and do not invent unrelated functionality. "
    "Your entire reply must be a single JSON object — no prose, no markdown, "
    "no code fences, no comments, no surrounding text — that conforms exactly "
    "to the schema described in the user message. "
    "If you cannot produce a plan, return the closest valid JSON you can; "
    "never return free-form text."
)


def build_planning_prompt(brief: str) -> str:
    """Build the user prompt containing the brief and the expected JSON schema.

    The prompt is intentionally strict about output format (JSON only) and
    about planning quality: grounded scope, sensible cardinality, unique ids,
    resolvable references, realistic implementation-order dependencies, and
    useful acceptance criteria.
    """
    return f"""Generate a structured project plan for the following project brief.

PROJECT BRIEF
-------------
{brief}

OUTPUT FORMAT
-------------
Return ONLY a single JSON object — no markdown, no code fences (no ```),
no prose, no comments, no trailing text. The JSON must conform exactly to the
schema below. Anything else will be rejected.

OUTPUT JSON SCHEMA
------------------
{{
  "project": {{
    "name": "Short project name derived from the brief",
    "summary": "Two or three sentences summarizing the project objective"
  }},
  "requirements": [
    {{"id": 1, "title": "Requirement title", "description": "What this requirement entails"}}
  ],
  "modules": [
    {{"id": 1, "name": "Module name", "description": "What this module covers"}}
  ],
  "tasks": [
    {{
      "id": 1,
      "module_id": 1,
      "requirement_id": 1,
      "title": "Actionable task title",
      "description": "What to build and why",
      "priority": "HIGH",
      "status": "TODO",
      "acceptance_criteria": ["Criterion 1", "Criterion 2"]
    }}
  ],
  "dependencies": [
    {{"task_id": 2, "depends_on": 1}}
  ]
}}

PLANNING RULES
--------------
1. Scope. Extract the explicit requirements from the brief and add only
   reasonable implied ones. Do not invent unnecessary requirements or
   functionality that is unrelated to the brief.
2. Cardinality. Adapt the plan to the complexity of the brief: prefer 3-8
   major requirements and 3-8 modules. A small brief (e.g. a todo app) should
   produce a small plan; a large brief should produce a fuller one. Do not
   always produce the same number.
3. Tasks. Break the work into implementation tasks that are specific,
   actionable, reasonably sized, and technically meaningful for real software
   development (for example: schema/database work, API endpoints, UI screens,
   validation, tests). Map every task to the module and requirement it belongs
   to. Generate enough tasks to make the plan useful, but avoid excessive task
   fragmentation and do not create duplicate tasks.
4. Priority. Assign each task exactly one of: HIGH, MEDIUM, LOW.
5. Status. Assign each task exactly one of: TODO, IN_PROGRESS, BLOCKED, DONE.
   Most planned work starts as TODO; use IN_PROGRESS, BLOCKED, or DONE only
   when the brief clearly implies already-completed or partially completed
   work.
6. Acceptance criteria. Give every task 1-3 concrete, verifiable acceptance
   criteria that a developer or tester could check.
7. Dependencies. Add a dependency only when one task genuinely must be built
   before another, and prefer realistic implementation order. Example:
   "Database schema" -> "Authentication API" -> "Authentication UI" ->
   "Protected dashboard". Avoid meaningless or speculative dependencies; a
   task must never depend on itself.
8. References. Use unique integer ids for requirements, modules, and tasks.
   Every module_id and requirement_id on a task must reference an entry
   defined above, and every dependency (task_id and depends_on) must reference
   an existing task id. Keep requirement/module/task relationships consistent.

Return only the JSON object."""
