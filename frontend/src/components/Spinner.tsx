interface SpinnerProps {
  label?: string
}

export function Spinner({ label }: SpinnerProps) {
  return (
    <div className="spinner-wrap" role="status">
      <span className="spinner" aria-hidden="true" />
      {label && <span>{label}</span>}
    </div>
  )
}
