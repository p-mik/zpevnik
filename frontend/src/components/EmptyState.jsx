import './ui.css'

// Prázdná obrazovka je pozvánka k akci, ne mrtvý bod.
export default function EmptyState({ title, description, actionLabel, onAction, actionHref }) {
  return (
    <div className="state-block">
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      {actionLabel && onAction && (
        <button type="button" className="btn btn-primary" onClick={onAction}>
          {actionLabel}
        </button>
      )}
      {actionLabel && actionHref && (
        <a className="btn btn-primary" href={actionHref}>
          {actionLabel}
        </a>
      )}
    </div>
  )
}
