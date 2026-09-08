import './ui.css'

export default function LoadingState({ label = 'Načítání…' }) {
  return (
    <div className="state-block" role="status" aria-live="polite">
      <span className="loading-pulse">{label}</span>
    </div>
  )
}
