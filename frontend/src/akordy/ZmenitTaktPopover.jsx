import { useState } from 'react'
import { TAKTY_PRESETY } from './akordovyModel'
import './RepeticePopover.css'
// `.akordy-takt-preset*` sdílené s hlavičkou (stejné volby taktu, viz tam).
import './AkordovyHlavicka.css'

// "Změnit takt" nad výběrem (zarovnaným na celé takty, viz volající) —
// stejné volby jako nahoře v hlavičce plus "Výchozí", který přepis zruší.
export default function ZmenitTaktPopover({ onPotvrdit, onZrusit }) {
  const [vlastniOtevreny, setVlastniOtevreny] = useState(false)
  const [vlastniDob, setVlastniDob] = useState('4')
  const [vlastniHodnota, setVlastniHodnota] = useState('4')

  function potvrdVlastni() {
    const d = Number(vlastniDob)
    const h = Number(vlastniHodnota)
    if (!Number.isInteger(d) || d < 1 || d > 32 || !Number.isInteger(h) || h < 1 || h > 32) return
    onPotvrdit({ dob: d, hodnota: h })
  }

  return (
    <div className="repetice-popover" role="dialog" aria-label="Změnit takt výběru">
      <span className="field-label">Nový takt pro vybrané takty</span>
      <div className="akordy-takt-presety" role="group" aria-label="Takt">
        {TAKTY_PRESETY.map((p) => (
          <button
            key={p.popisek}
            type="button"
            className="akordy-takt-preset"
            onClick={() => onPotvrdit({ dob: p.dob, hodnota: p.hodnota })}
          >
            {p.popisek}
          </button>
        ))}
        <button
          type="button"
          className="akordy-takt-preset"
          onClick={() => onPotvrdit(null)}
          title="Zruší vlastní přepis, takt bude sledovat výchozí"
        >
          Výchozí
        </button>
        <button
          type="button"
          className={`akordy-takt-preset${vlastniOtevreny ? ' akordy-takt-preset-aktivni' : ''}`}
          onClick={() => setVlastniOtevreny((v) => !v)}
        >
          Vlastní…
        </button>
      </div>
      {vlastniOtevreny && (
        <div className="akordy-takt-vlastni">
          <input
            type="number"
            className="field-input"
            min={1}
            max={32}
            value={vlastniDob}
            onChange={(e) => setVlastniDob(e.target.value)}
            aria-label="Počet dob v taktu"
          />
          <span>/</span>
          <input
            type="number"
            className="field-input"
            min={1}
            max={32}
            value={vlastniHodnota}
            onChange={(e) => setVlastniHodnota(e.target.value)}
            aria-label="Hodnota doby"
          />
          <button type="button" className="btn btn-primary" onClick={potvrdVlastni}>
            Použít
          </button>
        </div>
      )}
      <div className="repetice-popover-akce">
        <button type="button" className="btn btn-secondary" onClick={onZrusit}>
          Zrušit
        </button>
      </div>
    </div>
  )
}
