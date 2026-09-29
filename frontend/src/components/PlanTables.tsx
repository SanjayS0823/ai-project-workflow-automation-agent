import { Link } from 'react-router-dom'
import type { PlanModule, PlanRequirement, PlanTask } from '../types'
import { PriorityBadge, StatusBadge } from './Badge'

export function RequirementsTable({ requirements }: { requirements: PlanRequirement[] }) {
  if (requirements.length === 0) {
    return <EmptyRow text="No requirements in this plan." />
  }
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Title</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {requirements.map((requirement) => (
            <tr key={requirement.id}>
              <td className="cell-id">{requirement.id}</td>
              <td>{requirement.title}</td>
              <td className="cell-muted">{requirement.description || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ModulesTable({ modules }: { modules: PlanModule[] }) {
  if (modules.length === 0) {
    return <EmptyRow text="No modules in this plan." />
  }
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>Module Name</th>
            <th>Description</th>
            <th>Task Count</th>
          </tr>
        </thead>
        <tbody>
          {modules.map((module) => (
            <tr key={module.id}>
              <td>{module.name}</td>
              <td className="cell-muted">{module.description || '—'}</td>
              <td className="cell-num">{module.task_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export interface TaskFilters {
  priority: string
  status: string
  module: string
}

interface TasksTableProps {
  tasks: PlanTask[]
  filters: TaskFilters
  onFiltersChange: (filters: TaskFilters) => void
  modules: PlanModule[]
  projectId: string
}

export function TasksTable({
  tasks,
  filters,
  onFiltersChange,
  modules,
  projectId,
}: TasksTableProps) {
  const filtered = tasks.filter(
    (task) =>
      (filters.priority === 'ALL' || task.priority === filters.priority) &&
      (filters.status === 'ALL' || task.status === filters.status) &&
      (filters.module === 'ALL' || String(task.module_id) === filters.module),
  )

  const statusOptions = [...new Set(tasks.map((task) => task.status))].sort()
  const priorityOptions = ['HIGH', 'MEDIUM', 'LOW'].filter((value) =>
    tasks.some((task) => task.priority === value),
  )

  return (
    <div className="tasks-panel">
      <div className="filter-row">
        <label>
          Priority
          <select
            value={filters.priority}
            onChange={(event) => onFiltersChange({ ...filters, priority: event.target.value })}
          >
            <option value="ALL">All</option>
            {priorityOptions.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select
            value={filters.status}
            onChange={(event) => onFiltersChange({ ...filters, status: event.target.value })}
          >
            <option value="ALL">All</option>
            {statusOptions.map((value) => (
              <option key={value} value={value}>
                {value.replace('_', ' ')}
              </option>
            ))}
          </select>
        </label>
        <label>
          Module
          <select
            value={filters.module}
            onChange={(event) => onFiltersChange({ ...filters, module: event.target.value })}
          >
            <option value="ALL">All</option>
            {modules.map((module) => (
              <option key={module.id} value={module.id}>
                {module.name}
              </option>
            ))}
          </select>
        </label>
        <span className="filter-count">
          {filtered.length} of {tasks.length} tasks
        </span>
      </div>

      {filtered.length === 0 ? (
        <EmptyRow text="No tasks match the selected filters." />
      ) : (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Task ID</th>
                <th>Title</th>
                <th>Module</th>
                <th>Priority</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((task) => (
                <tr key={task.id}>
                  <td className="cell-id">#{task.id}</td>
                  <td>
                    <Link to={`/projects/${projectId}/tasks/${task.id}`}>
                      {task.title}
                    </Link>
                  </td>
                  <td>{task.module_name || '—'}</td>
                  <td>
                    <PriorityBadge priority={task.priority} />
                  </td>
                  <td>
                    <StatusBadge status={task.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

interface DependenciesTableProps {
  tasks: PlanTask[]
  dependencies: { task_id: number; depends_on_task_id: number }[]
}

export function DependenciesTable({ tasks, dependencies }: DependenciesTableProps) {
  const byId = new Map(tasks.map((task) => [task.id, task]))
  const rows = dependencies
    .map((dep) => ({
      task: byId.get(dep.task_id),
      dependsOn: byId.get(dep.depends_on_task_id),
    }))
    .filter((row): row is { task: PlanTask; dependsOn: PlanTask } => Boolean(row.task && row.dependsOn))
    .sort((a, b) => a.task.id - b.task.id)

  if (rows.length === 0) {
    return <EmptyRow text="No task dependencies in this plan." />
  }
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr>
            <th>Task</th>
            <th>Depends On</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.task.id}-${row.dependsOn.id}`}>
              <td>
                #{row.task.id} — {row.task.title}
              </td>
              <td>
                #{row.dependsOn.id} — {row.dependsOn.title}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function EmptyRow({ text }: { text: string }) {
  return <p className="empty-text panel-empty">{text}</p>
}
