import { useState } from 'react'
import { TAKTY_PRESETY, zpusobiZtratuZmenaVychozihoTaktu } from './akordovyModel'
import './AkordovyHlavicka.css'

// Takt a tempo. Změna VÝCHOZÍHO taktu mění jen takty BEZ vlastního přepisu
// (viz zadání bod 2) — počet taktů se neměnní, takže repetice zůstávají
// beze změny. Potvrzovací dialog se ptá JEN když by zúžení počtu dob
// zahodilo neprázdný obsah (buňky se jinak jen doplní/ořežou zprava).
export default function AkordovyHlavicka({ takt, tempo, sekce, onZmenTakt, onZmenTempo }) {
  const [vlastniOtevreny, setVlastniOtevreny] = useState(false)
  const [vlastniDob, setVlastniDob] = useState(String(takt.dob))
  const [vlastniHodnota, setVlastniHodnota] = useState(String(takt.hodnota))

  function pozadatOZmenu(novyDob, novaHodnota) {
    if (novyDob === takt.dob && novaHodnota === takt.hodnota) return
    if (
      zpusobiZtratuZmenaVychozihoTaktu(sekce, novyDob) &&
      !window.confirm(
        `Zúžení výchozího taktu na ${novyDob} dob zahodí obsah buněk, které se do nového ` +
          'počtu nevejdou (jen u taktů bez vlastního přepisu). Počet taktů ani repetice se neztratí. Pokračovat?',
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
