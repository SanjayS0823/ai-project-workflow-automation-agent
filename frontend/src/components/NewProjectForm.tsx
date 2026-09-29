import { useState, type FormEvent } from 'react'
import { ApiError, apiPost } from '../api'
import type { Project, ProjectPlan } from '../types'

interface NewProjectFormProps {
  onGenerated: (project: Project, plan: ProjectPlan) => void
}

export function NewProjectForm({ onGenerated }: NewProjectFormProps) {
  const [name, setName] = useState('')
  const [brief, setBrief] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const canSubmit = name.trim().length > 0 && brief.trim().length > 0 && !loading

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!canSubmit) return

    setLoading(true)
    setError(null)
    try {
      // Frontend -> Backend -> AI Planner -> Database -> Response
      const project = await apiPost<Project>('/api/projects', {
        name: name.trim(),
        original_brief: brief.trim(),
      })
      const plan = await apiPost<ProjectPlan>(
        `/api/projects/${project.id}/generate-plan`,
        { brief: brief.trim() },
      )
      onGenerated(project, plan)
      setName('')
      setBrief('')
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : 'Unable to generate the project plan. Please try again.',
      )
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="card form-card" aria-label="Create a new project">
      <h2>New Project</h2>
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="project-name">Project Name</label>
          <input
            id="project-name"
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. E-commerce Platform"
            maxLength={200}
            disabled={loading}
            required
          />
        </div>

        <div className="field">
          <label htmlFor="project-brief">Project Brief</label>
          <textarea
            id="project-brief"
            value={brief}
            onChange={(event) => setBrief(event.target.value)}
            placeholder="Describe the project in natural language, e.g. Build an e-commerce application where users can register, browse products, add products to a cart, and place orders."
            rows={5}
            maxLength={20000}
            disabled={loading}
            required
          />
        </div>

        {error && <p className="error-message" role="alert">{error}</p>}

        <button type="submit" className="primary" disabled={!canSubmit}>
          {loading ? 'Generating project plan…' : 'Generate Project Plan'}
        </button>
        {loading && (
          <p className="hint" role="status">
            Analyzing the brief, planning modules and tasks…
          </p>
        )}
      </form>
    </section>
  )
}
