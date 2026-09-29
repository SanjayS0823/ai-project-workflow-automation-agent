import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, apiGet } from '../api'
import { NewProjectForm } from '../components/NewProjectForm'
import { ProjectList } from '../components/ProjectList'
import { Spinner } from '../components/Spinner'
import type { Project, ProjectListItem, ProjectPlan } from '../types'

export function HomePage() {
  const [projects, setProjects] = useState<ProjectListItem[] | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [success, setSuccess] = useState<ProjectPlan | null>(null)

  const loadProjects = useCallback(async () => {
    setListError(null)
    try {
      const data = await apiGet<ProjectListItem[]>('/api/projects')
      setProjects(data)
    } catch (err) {
      setListError(
        err instanceof ApiError
          ? err.message
          : 'Unable to load projects. Please try again.',
      )
    }
  }, [])

  useEffect(() => {
    void loadProjects()
  }, [loadProjects])

  function handleGenerated(_project: Project, plan: ProjectPlan) {
    setSuccess(plan)
    void loadProjects()
  }

  return (
    <div className="app-shell">
      <header className="page-header">
        <h1>Projects</h1>
        <p className="subtitle">Plan projects from a natural-language brief.</p>
      </header>

      <main className="app-main">
        {success && (
          <div className="success-banner" role="status">
            <p>
              <strong>Plan generated.</strong> {success.tasks.length} tasks across{' '}
              {success.modules.length} modules for “{success.project.name}”.
            </p>
            <div className="success-actions">
              <Link className="button secondary" to={`/projects/${success.project.id}`}>
                View dashboard
              </Link>
              <button
                type="button"
                className="dismiss"
                onClick={() => setSuccess(null)}
                aria-label="Dismiss"
              >
                ×
              </button>
            </div>
          </div>
        )}

        <NewProjectForm onGenerated={handleGenerated} />

        <section className="projects-section" aria-label="Existing projects">
          <h2>Projects</h2>
          {listError ? (
            <div className="error-state" role="alert">
              <p>{listError}</p>
              <button type="button" className="secondary" onClick={() => void loadProjects()}>
                Retry
              </button>
            </div>
          ) : projects === null ? (
            <Spinner label="Loading projects…" />
          ) : (
            <ProjectList projects={projects} />
          )}
        </section>
      </main>
    </div>
  )
}
