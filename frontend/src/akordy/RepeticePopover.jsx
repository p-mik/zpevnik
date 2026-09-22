import { useState } from 'react'
import './RepeticePopover.css'

// Malé, neblokující okénko — "zeptá se na počet" ze zadání. Žádný modál:
// stejná lehká váha jako zbytek editoru (viz AnnotationToolbar).
export default function RepeticePopover({ onPotvrdit, onZrusit }) {
  const [krat, setKrat] = useState(2)

  return (
    <div className="repetice-popover" role="dialog" aria-label="Počet opakování">
      <label className="field-label" htmlFor="repetice-krat">
        Kolikrát se má úsek opakovat?
      </label>
      <input
        id="repetice-krat"
        type="number"
        className="field-input"
        min={2}
        max={16}
        value={krat}
        autoFocus
        onChange={(e) => setKrat(Number(e.target.value))}
        onKeyDown={(e) => {
          if (e.key === 'Enter') onPotvrdit(krat)
          if (e.key === 'Escape') onZrusit()
        }}
      />
      <div className="repetice-popover-akce">
        <button type="button" className="btn btn-primary" onClick={() => onPotvrdit(krat)}>
          Přidat repetici
        </button>
        <button type="button" className="btn btn-secondary" onClick={onZrusit}>
          Zrušit
        </button>
      </div>
    </div>
  )
}
