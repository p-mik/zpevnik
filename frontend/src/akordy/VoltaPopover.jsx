import { useState } from 'react'
import './VoltaPopover.css'

// Malé, neblokující okénko pro výběr čísla volty (1–4) — stejný lehký
// vzor jako RepeticePopover.
export default function VoltaPopover({ onPotvrdit, onZrusit }) {
  const [cislo, setCislo] = useState(1)

  return (
    <div className="volta-popover" role="dialog" aria-label="Číslo volty">
      <label className="field-label" htmlFor="volta-cislo">
        Číslo volty (jiný závěr při 1./2. průchodu)
      </label>
      <input
        id="volta-cislo"
        type="number"
        className="field-input"
        min={1}
        max={4}
        value={cislo}
        autoFocus
        onChange={(e) => setCislo(Number(e.target.value))}
        onKeyDown={(e) => {
          if (e.key === 'Enter') onPotvrdit(cislo)
          if (e.key === 'Escape') onZrusit()
        }}
      />
      <div className="volta-popover-akce">
        <button type="button" className="btn btn-primary" onClick={() => onPotvrdit(cislo)}>
          Přidat voltu
        </button>
        <button type="button" className="btn btn-secondary" onClick={onZrusit}>
          Zrušit
        </button>
      </div>
    </div>
  )
}
