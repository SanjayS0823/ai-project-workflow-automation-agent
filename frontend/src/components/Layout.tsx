import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation, useParams } from 'react-router-dom'
import { apiGet } from '../api'
import type { Project } from '../types'

const PROJECT_TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'requirements', label: 'Requirements' },
  { key: 'modules', label: 'Modules' },
  { key: 'tasks', label: 'Tasks' },
  { key: 'dependencies', label: 'Dependencies' },
]

export function Layout() {
  const { projectId } = useParams<{ projectId: string }>()
  const location = useLocation()
  const [project, setProject] = useState<Project | null>(null)

  useEffect(() => {
    let cancelled = false
    setProject(null)
    if (!projectId) return
    apiGet<Project>(`/api/projects/${projectId}`)
      .then((data) => {
        if (!cancelled) setProject(data)
      })
      .catch(() => {
        // Sidebar simply shows no project context.
      })
    return () => {
      cancelled = true
    }
  }, [projectId])

  const searchParams = new URLSearchParams(location.search)
  const activeTab = searchParams.get('tab') ?? 'overview'
  const onDashboard = location.pathname === `/projects/${projectId}`

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-mark" aria-hidden="true" />
          <div className="brand-text">
            <strong>AI Project &amp; Workflow</strong>
            <span>Automation Agent</span>
          </div>
        </div>

        <nav className="sidebar-nav" aria-label="Main navigation">
          <Link
            to="/"
            className={`sidebar-link ${location.pathname === '/' ? 'active' : ''}`}
          >
            Projects
          </Link>
        </nav>

        {project && (
          <div className="sidebar-section">
            <div className="sidebar-section-label">Project</div>
            <p className="sidebar-project-name" title={project.name}>
              {project.name}
            </p>
            <nav className="sidebar-nav" aria-label="Project sections">
              {PROJECT_TABS.map((tab) => (
                <Link
                  key={tab.key}
                  to={`/projects/${project.id}?tab=${tab.key}`}
                  className={`sidebar-link ${onDashboard && activeTab === tab.key ? 'active' : ''}`}
                >
                  {tab.label}
                </Link>
              ))}
            </nav>
          </div>
        )}

        <div className="sidebar-footer">Zenera Labs · Internal tool</div>
      </aside>

      <div className="content">
        <Outlet />
      </div>
    </div>
  )
}
