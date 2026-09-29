import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { ApiError, apiGet } from '../api'
import { Spinner } from '../components/Spinner'
import { Tabs } from '../components/Tabs'
import {
  DependenciesTable,
  ModulesTable,
  RequirementsTable,
  TasksTable,
  type TaskFilters,
} from '../components/PlanTables'
import type { ProjectPlan } from '../types'

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'requirements', label: 'Requirements' },
  { key: 'modules', label: 'Modules' },
  { key: 'tasks', label: 'Tasks' },
  { key: 'dependencies', label: 'Dependencies' },
]

const EMPTY_FILTERS: TaskFilters = { priority: 'ALL', status: 'ALL', module: 'ALL' }

export function DashboardPage() {
  const { projectId } = useParams<{ projectId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const [plan, setPlan] = useState<ProjectPlan | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState(() => searchParams.get('tab') ?? 'overview')
  const [filters, setFilters] = useState<TaskFilters>(EMPTY_FILTERS)

  function handleTabChange(key: string) {
    setActiveTab(key)
    setSearchParams({ tab: key }, { replace: true })
  }

  // Keep the active tab in sync with the URL (?tab=) so sidebar deep-links
  // work even when already on this dashboard.
  useEffect(() => {
    setActiveTab(searchParams.get('tab') ?? 'overview')
  }, [searchParams])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    setPlan(null)
    setFilters(EMPTY_FILTERS)

    apiGet<ProjectPlan>(`/api/projects/${projectId}/plan`)
      .then((data) => {
        if (!cancelled) setPlan(data)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? err.message
              : 'Unable to load the project plan. Please try again.',
          )
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [projectId])

  const stats = useMemo(() => {
    if (!plan) return null
    return {
      requirements: plan.requirements.length,
      modules: plan.modules.length,
      tasks: plan.tasks.length,
      highPriority: plan.tasks.filter((task) => task.priority === 'HIGH').length,
    }
  }, [plan])

  if (loading) {
    return (
      <div className="page-center">
        <Spinner label="Loading plan…" />
      </div>
    )
  }

  if (error || !plan || !stats) {
    return (
      <div className="page-center">
        <div className="error-state" role="alert">
          <p>{error ?? 'Unable to load the project plan.'}</p>
        </div>
        <Link className="secondary" to="/">
          Back to projects
        </Link>
      </div>
    )
  }

  return (
    <div className="app-shell">
      <header className="app-header dashboard-header">
        <div className="dashboard-heading">
          <Link className="back-link" to="/">
            ← Projects
          </Link>
          <div>
            <h1>{plan.project.name}</h1>
            {plan.project.description && (
              <p className="subtitle">{plan.project.description}</p>
            )}
          </div>
        </div>
      </header>

      <main className="app-main">
        <div className="stat-grid">
          <div className="stat-card">
            <span className="stat-value">{stats.requirements}</span>
            <span className="stat-label">Requirements</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">{stats.modules}</span>
            <span className="stat-label">Modules</span>
          </div>
          <div className="stat-card">
            <span className="stat-value">{stats.tasks}</span>
            <span className="stat-label">Tasks</span>
          </div>
          <div className="stat-card">
            <span className="stat-value stat-high">{stats.highPriority}</span>
            <span className="stat-label">High Priority Tasks</span>
          </div>
        </div>

        <Tabs tabs={TABS} active={activeTab} onChange={handleTabChange} />

        {activeTab === 'overview' && (
          <section className="card">
            <h2>Project Summary</h2>
            <p className="overview-text">{plan.project.description || 'No summary available.'}</p>
            {plan.project.original_brief && (
              <>
                <h3>Original Brief</h3>
                <p className="overview-text brief-text">{plan.project.original_brief}</p>
              </>
            )}
            <h3>Modules at a glance</h3>
            {plan.modules.length === 0 ? (
              <p className="empty-text">No modules in this plan.</p>
            ) : (
              <ul className="module-overview">
                {plan.modules.map((module) => (
                  <li key={module.id}>
                    <strong>{module.name}</strong>
                    <span className="cell-muted">{module.task_count} tasks</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}

        {activeTab === 'requirements' && (
          <section className="card">
            <h2>Requirements</h2>
            <RequirementsTable requirements={plan.requirements} />
          </section>
        )}

        {activeTab === 'modules' && (
          <section className="card">
            <h2>Modules</h2>
            <ModulesTable modules={plan.modules} />
          </section>
        )}

        {activeTab === 'tasks' && (
          <section className="card">
            <h2>Tasks</h2>
            <TasksTable
              tasks={plan.tasks}
              modules={plan.modules}
              filters={filters}
              onFiltersChange={setFilters}
              projectId={projectId ?? ''}
            />
          </section>
        )}

        {activeTab === 'dependencies' && (
          <section className="card">
            <h2>Dependencies</h2>
            <DependenciesTable tasks={plan.tasks} dependencies={plan.dependencies} />
          </section>
        )}
      </main>
    </div>
  )
}
