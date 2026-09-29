import { Link } from 'react-router-dom'
import type { ProjectListItem } from '../types'

interface ProjectListProps {
  projects: ProjectListItem[]
}

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function ProjectList({ projects }: ProjectListProps) {
  if (projects.length === 0) {
    return (
      <div className="empty-state">
        <p className="empty-title">No projects yet</p>
        <p className="empty-text">
          Create your first project above and generate its plan.
        </p>
      </div>
    )
  }

  return (
    <ul className="project-grid">
      {projects.map((project) => (
        <li key={project.id}>
          <Link className="card project-card" to={`/projects/${project.id}`}>
            <div className="project-card-header">
              <h3>{project.name}</h3>
              <span className="created-date">{formatDate(project.created_at)}</span>
            </div>
            {project.description && (
              <p className="project-description">{project.description}</p>
            )}
            <div className="stat-row">
              <span className="stat">
                <strong>{project.requirements_count}</strong> requirements
              </span>
              <span className="stat">
                <strong>{project.modules_count}</strong> modules
              </span>
              <span className="stat">
                <strong>{project.tasks_count}</strong> tasks
              </span>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  )
}
