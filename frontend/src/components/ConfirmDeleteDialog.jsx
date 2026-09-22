import { useState } from 'react'
import './ConfirmDeleteDialog.css'

// Potvrzovací dialog pro nevratné mazání (píseň/zpěvník, viz
// PC_zpevnik_sprava.md bod 5) — stejná lehká váha jako RepeticePopover
// (inline panel, ne modál přes celou obrazovku). Potvrzení vyžaduje
// PŘESNÝ opis názvu toho, co mizí — žádné jedno-kliknutí na nevratnou akci.
export default function ConfirmDeleteDialog({
  nazev,
  title,
  children,
  mazani,
  chyba,
  onPotvrdit,
  onZrusit,
}) {
  const [opis, setOpis] = useState('')
  const shoduje = opis === nazev

  return (
    <div className="confirm-delete-dialog" role="dialog" aria-label={title}>
      <h2 className="confirm-delete-title">{title}</h2>
      <div className="confirm-delete-obsah">{children}</div>

      <label className="field-label" htmlFor="confirm-delete-opis">
        Pro potvrzení opiš přesně „{nazev}“
      </label>
      <input
        id="confirm-delete-opis"
        type="text"
        className="field-input"
        value={opis}
        onChange={(e) => setOpis(e.target.value)}
        autoFocus
        autoComplete="off"
        onKeyDown={(e) => {
          if (e.key === 'Escape') onZrusit()
        }}
      />

      {chyba && (
        <p className="akordy-editor-chyba" role="alert">
          {chyba}
        </p>
      )}

      <div className="confirm-delete-akce">
        <button
          type="button"
          className="btn confirm-delete-btn"
          disabled={!shoduje || mazani}
          onClick={onPotvrdit}
        >
          {mazani ? 'Mažu…' : 'Nevratně smazat'}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onZrusit} disabled={mazani}>
          Zrušit
        </button>
      </div>
    </div>
  )
}
