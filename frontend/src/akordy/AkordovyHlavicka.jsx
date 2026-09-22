import { useState } from 'react'
import { TAKTY_PRESETY } from './akordovyModel'
import './AkordovyHlavicka.css'

// Takt a tempo. Změna taktu nad NEPRÁZDNÝM zápisem je jednosměrná ztráta
// (repetice se zahodí, viz akordovyModel.preskladejNaNovyTakt) — proto vždy
// potvrzovací dialog s vysvětlením, ne tichá změna. Nad prázdným zápisem
// (žádné řádky) se mění bez ptaní.
export default function AkordovyHlavicka({ takt, tempo, maRadky, onZmenTakt, onZmenTempo }) {
  const [vlastniOtevreny, setVlastniOtevreny] = useState(false)
  const [vlastniDob, setVlastniDob] = useState(String(takt.dob))
  const [vlastniHodnota, setVlastniHodnota] = useState(String(takt.hodnota))

  function pozadatOZmenu(novyDob, novaHodnota) {
    if (novyDob === takt.dob && novaHodnota === takt.hodnota) return
    if (
      maRadky &&
      !window.confirm(
        'Změna taktu přeskládá čáry taktů podle nového dělení — buňky (akordy) zůstanou, ' +
          'jen se přeskupí. Existující repetice se přitom zruší (odkazovaly na staré hranice taktů). Pokračovat?',
      )
    ) {
      return
    }
    onZmenTakt(novyDob, novaHodnota)
  }

  function potvrdVlastni() {
    const d = Number(vlastniDob)
    const h = Number(vlastniHodnota)
    if (!Number.isInteger(d) || d < 1 || d > 32 || !Number.isInteger(h) || h < 1 || h > 32) return
    pozadatOZmenu(d, h)
    setVlastniOtevreny(false)
  }

  return (
    <div className="akordy-hlavicka">
      <div className="akordy-hlavicka-pole">
        <span className="field-label">Takt</span>
        <div className="akordy-takt-presety" role="group" aria-label="Takt">
          {TAKTY_PRESETY.map((p) => (
            <button
              key={p.popisek}
              type="button"
              className={`akordy-takt-preset${
                takt.dob === p.dob && takt.hodnota === p.hodnota ? ' akordy-takt-preset-aktivni' : ''
              }`}
              onClick={() => pozadatOZmenu(p.dob, p.hodnota)}
              aria-pressed={takt.dob === p.dob && takt.hodnota === p.hodnota}
            >
              {p.popisek}
            </button>
          ))}
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
            <button type="button" className="btn btn-secondary" onClick={potvrdVlastni}>
              Použít
            </button>
          </div>
        )}
      </div>

      <div className="akordy-hlavicka-pole">
        <label className="field-label" htmlFor="akordy-tempo">
          Tempo (BPM)
        </label>
        <input
          id="akordy-tempo"
          type="number"
          className="field-input akordy-tempo-input"
          min={20}
          max={400}
          value={tempo ?? ''}
          placeholder="volitelné"
          onChange={(e) => onZmenTempo(e.target.value === '' ? null : Number(e.target.value))}
        />
      </div>
    </div>
  )
}
