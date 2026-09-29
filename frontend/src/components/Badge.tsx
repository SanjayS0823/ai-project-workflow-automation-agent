const PRIORITY_CLASSES: Record<string, string> = {
  HIGH: 'badge-danger',
  MEDIUM: 'badge-warning',
  LOW: 'badge-neutral',
}

const STATUS_CLASSES: Record<string, string> = {
  TODO: 'badge-neutral',
  IN_PROGRESS: 'badge-info',
  BLOCKED: 'badge-danger',
  DONE: 'badge-success',
}

export function PriorityBadge({ priority }: { priority: string }) {
  return (
    <span className={`badge ${PRIORITY_CLASSES[priority] ?? 'badge-neutral'}`}>
      {priority}
    </span>
  )
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge ${STATUS_CLASSES[status] ?? 'badge-neutral'}`}>
      {status.replace('_', ' ')}
    </span>
  )
}
