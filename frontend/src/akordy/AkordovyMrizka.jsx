import { useEffect, useRef, useState } from 'react'
import {
  SEKCE_NAVRHY,
  pocetTaktu,
  prepniVeVyberu,
  rozsahMeziPozicemi,
  vyberObsahuje,
  zkontrolujVyberProRepetici,
} from './akordovyModel'
import RepeticePopover from './RepeticePopover'
import './AkordovyMrizka.css'

// Mřížka akordového zápisu — editor, NE generovaný PDF (ten má vlastní,
// přesně kalibrovaný vzhled v zpevnik/akordy_pdf.py). Tady jde hlavně o
// rychlé psaní a navigaci klávesnicí, vizuál je jednodušší (posuvník
// místo vizuálního zalamování — víc taktů na řádek než se vejde na
// obrazovku prostě odscrolluje, žádné omezení na 4 takty jako v PDF).
//
// Klávesy (viz zadání):
//  Tab        další buňka; na konci řádku přidá nový takt a skočí do něj
//  Shift+Tab  předchozí buňka; přes hranici řádku do konce předchozího
//  Enter      nový řádek pod aktuálním (jeden prázdný takt), kurzor do 1. buňky
//  ↑ / ↓      stejná pozice v řádku nad/pod, jen když tam buňka existuje
// Backspace v prázdné buňce záměrně nic nemaže (viz zadání) — žádný handler.
export default function AkordovyMrizka({
  radky,
  dob,
  onUpravBunku,
  onNastavSekci,
  onPridejTakt,
  onSmazTakt,
  onSmazRadek,
  onVlozRadekPo,
  onPridejRadekNaKonec,
  onPridejRepetici,
  onSmazRepetici,
}) {
  const [vyber, setVyber] = useState([])
  const posledniKlikRef = useRef(null)
  const zamereniRef = useRef(null)
  const inputyRef = useRef(new Map())
  const [repeticeChyba, setRepeticeChyba] = useState(null)
  const [popoverOtevreny, setPopoverOtevreny] = useState(false)

  // Zaostření po akci, která mění DOM (přidání taktu/řádku) — provede se AŽ
  // po re-renderu, kdy nová buňka fakt existuje.
  useEffect(() => {
    if (!zamereniRef.current) return
    const klic = poziceKlic(zamereniRef.current)
    zamereniRef.current = null
    const el = inputyRef.current.get(klic)
    el?.focus()
  })

  function poziceKlic(p) {
    return `${p.radek}:${p.bunka}`
  }

  function refPro(radekIdx, bunkaIdx) {
    return (el) => {
      const klic = `${radekIdx}:${bunkaIdx}`
      if (el) inputyRef.current.set(klic, el)
      else inputyRef.current.delete(klic)
    }
  }

  function zaostrPo(pozice) {
    zamereniRef.current = pozice
  }

  function naKlavesu(e, radekIdx, bunkaIdx) {
    const radek = radky[radekIdx]

    if (e.key === 'Tab' && !e.shiftKey) {
      e.preventDefault()
      if (bunkaIdx === radek.bunky.length - 1) {
        onPridejTakt(radekIdx)
        zaostrPo({ radek: radekIdx, bunka: bunkaIdx + 1 })
      } else {
        inputyRef.current.get(`${radekIdx}:${bunkaIdx + 1}`)?.focus()
      }
      return
    }

    if (e.key === 'Tab' && e.shiftKey) {
      e.preventDefault()
      if (bunkaIdx > 0) {
        inputyRef.current.get(`${radekIdx}:${bunkaIdx - 1}`)?.focus()
      } else if (radekIdx > 0) {
        const predchozi = radky[radekIdx - 1]
        inputyRef.current.get(`${radekIdx - 1}:${predchozi.bunky.length - 1}`)?.focus()
      }
      return
    }

    if (e.key === 'Enter') {
      e.preventDefault()
      onVlozRadekPo(radekIdx)
      zaostrPo({ radek: radekIdx + 1, bunka: 0 })
      return
    }

    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      const cilRadekIdx = e.key === 'ArrowUp' ? radekIdx - 1 : radekIdx + 1
      const cilRadek = radky[cilRadekIdx]
      if (!cilRadek || cilRadek.bunky.length <= bunkaIdx) return
      e.preventDefault()
      inputyRef.current.get(`${cilRadekIdx}:${bunkaIdx}`)?.focus()
    }
  }

  function naKlikBunky(e, radekIdx, bunkaIdx) {
    const pozice = { radek: radekIdx, bunka: bunkaIdx }
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault()
      setVyber((prev) => prepniVeVyberu(prev, pozice))
      posledniKlikRef.current = pozice
      setRepeticeChyba(null)
    } else if (e.shiftKey && posledniKlikRef.current) {
      e.preventDefault()
      setVyber(rozsahMeziPozicemi(radky, posledniKlikRef.current, pozice))
      setRepeticeChyba(null)
    } else {
      // Obyčejný klik jen zaostří (přirozené chování inputu) a založí kotvu
      // pro případný příští Shift+klik — výběr nezakládá ani neruší.
      posledniKlikRef.current = pozice
    }
  }

  function otevriRepetici() {
    const kontrola = zkontrolujVyberProRepetici(vyber, radky, dob)
    if (!kontrola.ok) {
      setRepeticeChyba(kontrola.hlaska)
      return
    }
    setRepeticeChyba(null)
    setPopoverOtevreny(true)
  }

  function potvrdRepetici(krat) {
    const kontrola = zkontrolujVyberProRepetici(vyber, radky, dob)
    setPopoverOtevreny(false)
    if (!kontrola.ok) {
      setRepeticeChyba(kontrola.hlaska)
      return
    }
    onPridejRepetici(kontrola.indexRadku, kontrola.od_takt, kontrola.do_takt, krat)
    setVyber([])
  }

  return (
    <div className="akordy-mrizka">
      {radky.length === 0 && (
        <p className="akordy-prazdno">Zápis je zatím prázdný — přidej první řádek.</p>
      )}

      <ul className="akordy-radky">
        {radky.map((radek, radekIdx) => (
          <li key={radekIdx} className="akordy-radek">
            <input
              list="akordy-sekce-navrhy"
              className="field-input akordy-sekce-input"
              value={radek.sekce}
              placeholder="Sekce"
              onChange={(e) => onNastavSekci(radekIdx, e.target.value)}
              aria-label={`Sekce řádku ${radekIdx + 1}`}
            />

            <div className="akordy-takty" role="group" aria-label={`Takty řádku ${radekIdx + 1}`}>
              {Array.from({ length: pocetTaktu(radek, dob) }, (_, taktIdx) => (
                <div key={taktIdx} className="akordy-takt">
                  <button
                    type="button"
                    className="akordy-takt-smazat"
                    onClick={() => onSmazTakt(radekIdx, taktIdx)}
                    aria-label={`Smazat takt ${taktIdx + 1} řádku ${radekIdx + 1}`}
                    title="Smazat takt"
                  >
                    ×
                  </button>
                  <div className="akordy-takt-bunky">
                    {Array.from({ length: dob }, (_, doba) => {
                      const bunkaIdx = taktIdx * dob + doba
                      const pozice = { radek: radekIdx, bunka: bunkaIdx }
                      return (
                        <input
                          key={bunkaIdx}
                          ref={refPro(radekIdx, bunkaIdx)}
                          type="text"
                          className={`akordy-bunka${vyberObsahuje(vyber, pozice) ? ' akordy-bunka-vybrana' : ''}`}
                          value={radek.bunky[bunkaIdx]}
                          autoCorrect="off"
                          autoCapitalize="off"
                          spellCheck={false}
                          onChange={(e) => onUpravBunku(radekIdx, bunkaIdx, e.target.value)}
                          onKeyDown={(e) => naKlavesu(e, radekIdx, bunkaIdx)}
                          onClick={(e) => naKlikBunky(e, radekIdx, bunkaIdx)}
                          aria-label={`Doba ${doba + 1}, takt ${taktIdx + 1}, řádek ${radekIdx + 1}`}
                        />
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>

            <button
              type="button"
              className="btn akordy-radek-smazat"
              onClick={() => onSmazRadek(radekIdx)}
            >
              Smazat řádek
            </button>

            {radek.repetice.length > 0 && (
              <ul className="akordy-repetice-seznam" aria-label={`Repetice řádku ${radekIdx + 1}`}>
                {radek.repetice.map((rep, repIdx) => (
                  <li key={repIdx}>
                    <button
                      type="button"
                      className="akordy-repetice-chip"
                      onClick={() => onSmazRepetici(radekIdx, repIdx)}
                      title="Klikem odebrat"
                    >
                      takt {rep.od_takt + 1}–{rep.do_takt + 1} ×{rep.krat} ✕
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>

      <datalist id="akordy-sekce-navrhy">
        {SEKCE_NAVRHY.map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>

      <div className="akordy-mrizka-akce">
        <button type="button" className="btn btn-secondary" onClick={onPridejRadekNaKonec}>
          + Přidat řádek
        </button>
        {vyber.length > 0 && (
          <div className="akordy-vyber-akce">
            <span className="akordy-vyber-info">{vyber.length} vybraných buněk</span>
            <button type="button" className="btn btn-secondary" onClick={otevriRepetici}>
              Repetice
            </button>
            <button type="button" className="btn akordy-vyber-zrusit" onClick={() => setVyber([])}>
              Zrušit výběr
            </button>
          </div>
        )}
      </div>

      {repeticeChyba && (
        <p className="akordy-repetice-chyba" role="alert">
          {repeticeChyba}
        </p>
      )}

      {popoverOtevreny && (
        <RepeticePopover onPotvrdit={potvrdRepetici} onZrusit={() => setPopoverOtevreny(false)} />
      )}
    </div>
  )
}
