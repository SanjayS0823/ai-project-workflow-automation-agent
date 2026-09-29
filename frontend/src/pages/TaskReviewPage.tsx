import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, apiGet, apiPost, apiPut } from '../api'
import { PriorityBadge, StatusBadge } from '../components/Badge'
import { Spinner } from '../components/Spinner'
import type { PlanTask, ProjectPlan } from '../types'

const PRIORITIES = ['HIGH', 'MEDIUM', 'LOW']
const STATUSES = ['TODO', 'IN_PROGRESS', 'BLOCKED', 'DONE']

export function TaskReviewPage() {
  const { projectId, taskId } = useParams<{ projectId: string; taskId: string }>()
  const [plan, setPlan] = useState<ProjectPlan | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const task = useMemo(
    () => plan?.tasks.find((t) => String(t.id) === taskId) ?? null,
    [plan, taskId],
  )

  // Editable fields, initialized from the loaded task.
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState('MEDIUM')
  const [status, setStatus] = useState('TODO')
  const [criteria, setCriteria] = useState<string[]>([])

  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  // GitHub issue state (kept separate so creating an issue never wipes edits).
  const [issueUrl, setIssueUrl] = useState<string | null>(null)
  const [creatingIssue, setCreatingIssue] = useState(false)
  const [issueError, setIssueError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError(null)
    setPlan(null)

    apiGet<ProjectPlan>(`/api/projects/${projectId}/plan`)
      .then((data) => {
        if (!cancelled) setPlan(data)
      })
      .catch((err) => {
        if (!cancelled) {
          setLoadError(
            err instanceof ApiError
              ? err.message
              : 'Unable to load the task. Please try again.',
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

  useEffect(() => {
    if (task) {
      setTitle(task.title)
      setDescription(task.description ?? '')
      setPriority(task.priority)
      setStatus(task.status)
      setCriteria(task.acceptance_criteria.map((c) => c.criterion))
      setDirty(false)
      setSaved(false)
      setSaveError(null)
      setIssueUrl(task.github_issue_url ?? null)
      setCreatingIssue(false)
      setIssueError(null)
    }
  }, [task])

  if (loading) {
    return (
      <div className="page-center">
        <Spinner label="Loading task…" />
      </div>
    )
  }

  if (loadError || !task || !plan) {
    return (
      <div className="page-center">
        <div className="error-state" role="alert">
          <p>{loadError ?? 'Task not found.'}</p>
        </div>
        <Link className="secondary" to={`/projects/${projectId}`}>
          Back to dashboard
        </Link>
      </div>
    )
  }

  // `task` is guaranteed non-null past the guards above; alias it so the
  // narrowed type flows into the handler closure.
  const currentTask = task

  const dependencyTasks = currentTask.dependencies
    .map((id) => plan.tasks.find((t) => t.id === id))
    .filter((t): t is NonNullable<typeof t> => Boolean(t))

  const canSave = !saving && dirty && title.trim().length > 0

  async function handleSave() {
    setSaving(true)
    setSaveError(null)
    setSaved(false)
    try {
      await apiPut(`/api/tasks/${currentTask.id}`, {
        title: title.trim(),
        description,
        priority,
        status,
        acceptance_criteria: criteria.map((c) => c.trim()).filter(Boolean),
      })
      setDirty(false)
      setSaved(true)
    } catch (err) {
      setSaveError(
        err instanceof ApiError
          ? err.message
          : 'Unable to save the task. Please try again.',
      )
    } finally {
      setSaving(false)
    }
  }

  function updateCriteria(index: number, value: string) {
    setCriteria((current) => current.map((c, i) => (i === index ? value : c)))
    setDirty(true)
  }

  function addCriterion() {
    setCriteria((current) => [...current, ''])
    setDirty(true)
  }

  function removeCriterion(index: number) {
    setCriteria((current) => current.filter((_, i) => i !== index))
    setDirty(true)
  }

  async function handleCreateIssue() {
    // Explicit user confirmation before touching GitHub.
    if (!window.confirm('Create a GitHub issue for this task in the configured repository?')) {
      return
    }
    setCreatingIssue(true)
    setIssueError(null)
    try {
      const updated = await apiPost<PlanTask>(
        `/api/tasks/${currentTask.id}/github-issue`,
        {},
      )
      setIssueUrl(updated.github_issue_url)
    } catch (err) {
      setIssueError(
        err instanceof ApiError
          ? err.message
          : 'Unable to create the GitHub issue. Please try again.',
      )
    } finally {
      setCreatingIssue(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header dashboard-header">
        <div className="dashboard-heading">
          <Link className="back-link" to={`/projects/${projectId}`}>
            ← {plan.project.name}
          </Link>
          <div>
            <h1>
              Task #{task.id} — {title || task.title}
            </h1>
            <p className="subtitle">
              Module: {task.module_name || 'Unassigned'} · Requirement:{' '}
              {task.requirement_title || 'Unassigned'}
            </p>
          </div>
        </div>
      </header>

      <main className="app-main">
        <div className="ai-notice" role="note">
          <span className="badge badge-info">AI-generated</span>
          <p>
            This task was created by the AI planner from your project brief. It
            is editable — review it and adjust anything below. Changes are saved
            to the project plan.
          </p>
        </div>

        <div className="task-layout">
          <section className="card task-info">
            <h2>Details</h2>
            <dl className="info-grid">
              <div className="info-item">
                <dt>Task ID</dt>
                <dd>#{task.id}</dd>
              </div>
              <div className="info-item">
                <dt>Module</dt>
                <dd>{task.module_name || '—'}</dd>
              </div>
              <div className="info-item">
                <dt>Requirement</dt>
                <dd>{task.requirement_title || '—'}</dd>
              </div>
              <div className="info-item">
                <dt>Priority</dt>
                <dd>
                  <PriorityBadge priority={task.priority} />
                </dd>
              </div>
              <div className="info-item">
                <dt>Status</dt>
                <dd>
                  <StatusBadge status={task.status} />
                </dd>
              </div>
              <div className="info-item">
                <dt>Created</dt>
                <dd>{new Date(task.created_at).toLocaleDateString()}</dd>
              </div>
            </dl>

            <h3>Dependencies</h3>
            {dependencyTasks.length === 0 ? (
              <p className="empty-text">This task has no dependencies.</p>
            ) : (
              <ul className="dependency-list">
                {dependencyTasks.map((dep) => (
                  <li key={dep.id}>
                    #{dep.id} — {dep.title}
                  </li>
                ))}
              </ul>
            )}

            <div className="github-section">
              <h3>GitHub</h3>
              {issueUrl ? (
                <p className="hint">
                  Linked to{' '}
                  <a href={issueUrl} target="_blank" rel="noreferrer">
                    GitHub issue #{issueUrl.split('/').pop()}
                  </a>
                </p>
              ) : (
                <>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => void handleCreateIssue()}
                    disabled={creatingIssue}
                  >
                    {creatingIssue ? 'Creating GitHub issue…' : 'Create GitHub issue'}
                  </button>
                  <p className="hint">
                    Creates an issue in the configured repository. You will be
                    asked to confirm.
                  </p>
                </>
              )}
              {issueError && (
                <p className="error-message" role="alert">
                  {issueError}
                </p>
              )}
            </div>
          </section>

          <section className="card task-editor">
            <h2>Edit Task</h2>
            <form
              onSubmit={(event) => {
                event.preventDefault()
                void handleSave()
              }}
            >
              <div className="field">
                <label htmlFor="task-title">Title</label>
                <input
                  id="task-title"
                  type="text"
                  value={title}
                  onChange={(event) => {
                    setTitle(event.target.value)
                    setDirty(true)
                  }}
                  maxLength={300}
                />
              </div>

              <div className="field">
                <label htmlFor="task-description">Description</label>
                <textarea
                  id="task-description"
                  value={description}
                  onChange={(event) => {
                    setDescription(event.target.value)
                    setDirty(true)
                  }}
                  rows={4}
                />
              </div>

              <div className="field-row">
                <div className="field">
                  <label htmlFor="task-priority">Priority</label>
                  <select
                    id="task-priority"
                    value={priority}
                    onChange={(event) => {
                      setPriority(event.target.value)
                      setDirty(true)
                    }}
                  >
                    {PRIORITIES.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="task-status">Status</label>
                  <select
                    id="task-status"
                    value={status}
                    onChange={(event) => {
                      setStatus(event.target.value)
                      setDirty(true)
                    }}
                  >
                    {STATUSES.map((value) => (
                      <option key={value} value={value}>
                        {value.replace('_', ' ')}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="field">
                <label>Acceptance Criteria</label>
                <ul className="criteria-list">
                  {criteria.map((criterion, index) => (
                    <li key={index} className="criteria-row">
                      <input
                        type="text"
                        value={criterion}
                        onChange={(event) => updateCriteria(index, event.target.value)}
                        aria-label={`Acceptance criterion ${index + 1}`}
                      />
                      <button
                        type="button"
                        className="remove"
                        onClick={() => removeCriterion(index)}
                        aria-label={`Remove criterion ${index + 1}`}
                      >
                        Remove
                      </button>
                    </li>
                  ))}
                </ul>
                <button type="button" className="secondary" onClick={addCriterion}>
                  + Add criterion
                </button>
              </div>

              {saveError && (
                <p className="error-message" role="alert">
                  {saveError}
                </p>
              )}
              {saved && (
                <p className="success-message" role="status">
                  Changes saved.
                </p>
              )}

              <div className="form-actions">
                <button type="submit" className="primary" disabled={!canSave}>
                  {saving ? 'Saving…' : 'Save Changes'}
                </button>
                {dirty && <span className="hint">Unsaved changes</span>}
              </div>
            </form>
          </section>
        </div>
      </main>
    </div>
  )
}
