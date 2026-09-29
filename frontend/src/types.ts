// Types mirroring the backend API responses (see backend/app/schemas.py).

export interface Project {
  id: number
  name: string
  description: string | null
  original_brief: string | null
  created_at: string
  updated_at: string
}

export interface ProjectListItem extends Project {
  requirements_count: number
  modules_count: number
  tasks_count: number
}

export interface Criterion {
  id: number
  criterion: string
}

export interface PlanTask {
  id: number
  project_id: number
  module_id: number | null
  requirement_id: number | null
  title: string
  description: string | null
  priority: string
  status: string
  created_at: string
  updated_at: string
  module_name: string
  requirement_title: string
  acceptance_criteria: Criterion[]
  dependencies: number[]
  github_issue_url: string | null
}

export interface PlanModule {
  id: number
  name: string
  description: string
  task_count: number
}

export interface PlanRequirement {
  id: number
  title: string
  description: string
}

export interface PlanDependency {
  task_id: number
  depends_on_task_id: number
}

export interface ProjectPlan {
  project: Project
  requirements: PlanRequirement[]
  modules: PlanModule[]
  tasks: PlanTask[]
  dependencies: PlanDependency[]
}

export type TaskPriority = 'HIGH' | 'MEDIUM' | 'LOW'

export type TaskStatus = 'TODO' | 'IN_PROGRESS' | 'BLOCKED' | 'DONE'
