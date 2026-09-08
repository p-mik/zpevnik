import './ui.css'

export default function ErrorState({ message = 'Něco se nepovedlo.', onRetry }) {
  return (
    <div className="state-block state-error" role="alert">
      <h2>Chyba</h2>
      <p>{message}</p>
      {onRetry && (
        <button type="button" className="btn btn-secondary" onClick={onRetry}>
          Zkusit znovu
        </button>
      )}
    </div>
  )
}
