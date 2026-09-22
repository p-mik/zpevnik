import { useEffect, useRef, useState } from 'react'
import {
  SEKCE_NAVRHY,
  efektivniTakt,
  flatIndexZPozice,
  nejdelsiRadekVDobach,
  poziceVRadku,
  prepniVeVyberu,
  radekCelkemBunek,
  rozsahMeziPozicemi,
  vyberObsahuje,
  zkontrolujVyberProRepetici,
  zpusobiZtratuZmenaVyberu,
} from './akordovyModel'
import RepeticePopover from './RepeticePopover'
import ZmenitTaktPopover from './ZmenitTaktPopover'
import './AkordovyMrizka.css'

const MIN_SIRKA_BUNKY = 36

// Mřížka akordového zápisu — sekce jsou bloky (jméno jednou nahoře, pod
// ním řádky taktů), viz PC_zpevnik_akordovy_zapis_upravy.md bod 1. ŘÁDEK
// SE NIKDY SÁM NEZALAMUJE (bod 4) — delší řádek prostě odscrolluje
// vodorovně, PDF ho zmenší jako celek (viz info hláška dole).
//
// Klávesy:
//  Tab        další buňka; na konci řádku přidá nový takt a skočí do něj
//  Shift+Tab  předchozí buňka; přes hranici řádku (i sekce) do konce předchozího
//  Enter      nový řádek POD aktuálním, UVNITŘ TÉŽE SEKCE
//  ↑ / ↓      stejná pozice v řádku nad/pod (napříč celým zápisem), jen
//             když tam buňka existuje
export default function AkordovyMrizka({
  zapis,
  onUpravBunku,
  onNastavNazevSekce,
  onPridejTakt,
  onSmazTakt,
  onVlozRadekPo,
  onSmazSekci,
  onPridejSekci,
  onPridejRepetici,
  onSmazRepetici,
  onZmenTaktVyberu,
}) {
  const dob = zapis.takt.dob
  const [vyber, setVyber] = useState([])
  const posledniKlikRef = useRef(null)
  const zamereniRef = useRef({ typ: null, poz: null })
  const inputyRef = useRef(new Map())
  const nazvySekciRef = useRef(new Map())
  const [repeticeChyba, setRepeticeChyba] = useState(null)
  const [repeticePopoverOtevreny, setRepeticePopoverOtevreny] = useState(false)
  const [taktPopoverOtevreny, setTaktPopoverOtevreny] = useState(false)
  const [sirkaBunky, setSirkaBunky] = useState(64)
  const sondaRef = useRef(null)

  // Šířka buňky: 4 takty výchozího taktu se musí vejít na šířku řádku bez
  // scrollu (viz zadání bod 1). Hrubý odhad (šířka sloupce / počet dob)
  // nepočítá s mezerami mezi buňkami, oddělovači taktů (border-left) a
  // paddingem taktů — proto se koriguje přeměřením: rozdíl mezi skutečně
  // vykresleným scrollWidth a odhadem*počet_dob je ta "režie" (mezery +
  // oddělovače + padding), která NEZÁVISÍ na šířce buňky, takže jedna
  // korekce z reálně vykreslené šířky buňky stačí. Pod MIN_SIRKA_BUNKY je
  // scroll povolený (viz CSS).
  //
  // Měří se ze skryté SONDY (viz JSX níž), NE z prvního skutečného řádku —
  // ten často NEMÁ 4 takty (nová píseň má 1, po smazání taktů může mít
  // taky 1, viz bod 2), takže by "celkemDob = 4 * dob" nesedělo s tím, co
  // je doopravdy vykreslené, a přepočet by vyšel řádově mimo (to byl
  // skutečný důvod produkčního bugu, ne rozjezd webfontů — viz report).
  // Sonda má vždycky přesně 4 takty výchozího taktu, takže platí vždycky.
  useEffect(() => {
    const el = sondaRef.current
    if (!el) return undefined
    function prepocitej() {
      const celkemDob = 4 * dob
      if (celkemDob <= 0) return
      const prvniBunka = el.querySelector('.akordy-bunka')
      const aktualniSirkaBunky = prvniBunka
        ? prvniBunka.getBoundingClientRect().width
        : el.clientWidth / celkemDob
      const rezie = el.scrollWidth - celkemDob * aktualniSirkaBunky
      const presna = Math.max(MIN_SIRKA_BUNKY, (el.clientWidth - rezie) / celkemDob)
      setSirkaBunky(presna)
    }
    prepocitej()
    const ro = new ResizeObserver(prepocitej)
    ro.observe(el)
    // Pojistka pro případ, že by CSS/fonty dorazily až po prvním layoutu
    // (viz zadání) — i bez vlastního webfontu se může první měření strefit
    // do okna, kdy prohlížeč ještě nemá layout/fonty definitivně ustálené.
    let zruseno = false
    document.fonts?.ready?.then(() => {
      if (!zruseno) prepocitej()
    })
    return () => {
      zruseno = true
      ro.disconnect()
    }
  }, [dob])

  useEffect(() => {
    const { typ, poz } = zamereniRef.current
    if (!typ) return
    zamereniRef.current = { typ: null, poz: null }
    if (typ === 'bunka') {
      inputyRef.current.get(bunkaKlic(poz))?.focus()
    } else if (typ === 'sekce') {
      nazvySekciRef.current.get(poz)?.focus()
    }
  })

  function bunkaKlic(p) {
    return `${p.sekceIdx}:${p.radekIdx}:${p.taktIdx}:${p.dobaIdx}`
  }
  function refProBunku(p) {
    return (el) => {
      const klic = bunkaKlic(p)
      if (el) inputyRef.current.set(klic, el)
      else inputyRef.current.delete(klic)
    }
  }
  function zaostrBunku(sekceIdx, radekIdx, taktIdx, dobaIdx) {
    zamereniRef.current = { typ: 'bunka', poz: { sekceIdx, radekIdx, taktIdx, dobaIdx } }
  }
  function zaostrNazevSekce(sekceIdx) {
    zamereniRef.current = { typ: 'sekce', poz: sekceIdx }
  }

  // --- plochý seznam všech řádků dokumentu (pro šipky napříč sekcemi) ---
  function plochySeznamRadku() {
    const vysledek = []
    zapis.sekce.forEach((s, si) => s.radky.forEach((_, ri) => vysledek.push({ sekceIdx: si, radekIdx: ri })))
    return vysledek
  }

  function focusFlatVRadku(sekceIdx, radekIdx, flatIdx) {
    const radek = zapis.sekce[sekceIdx].radky[radekIdx]
    const p = poziceVRadku(radek, flatIdx)
    if (!p) return
    inputyRef.current.get(bunkaKlic({ sekceIdx, radekIdx, ...p }))?.focus()
  }

  function naKlavesu(e, sekceIdx, radekIdx, taktIdx, dobaIdx) {
    const radek = zapis.sekce[sekceIdx].radky[radekIdx]
    const flatIdx = flatIndexZPozice(radek, taktIdx, dobaIdx)
    const celkem = radekCelkemBunek(radek)

    if (e.key === 'Tab' && !e.shiftKey) {
      e.preventDefault()
      if (flatIdx === celkem - 1) {
        const novyTaktIdx = radek.takty.length
        onPridejTakt(sekceIdx, radekIdx)
        zaostrBunku(sekceIdx, radekIdx, novyTaktIdx, 0)
      } else {
        focusFlatVRadku(sekceIdx, radekIdx, flatIdx + 1)
      }
      return
    }

    if (e.key === 'Tab' && e.shiftKey) {
      e.preventDefault()
      if (flatIdx > 0) {
        focusFlatVRadku(sekceIdx, radekIdx, flatIdx - 1)
        return
      }
      // Na první buňce řádku — přes hranici řádku (i sekce) do konce předchozího.
      const seznam = plochySeznamRadku()
      const tady = seznam.findIndex((r) => r.sekceIdx === sekceIdx && r.radekIdx === radekIdx)
      if (tady > 0) {
        const predchozi = seznam[tady - 1]
        const predRadek = zapis.sekce[predchozi.sekceIdx].radky[predchozi.radekIdx]
        focusFlatVRadku(predchozi.sekceIdx, predchozi.radekIdx, radekCelkemBunek(predRadek) - 1)
      }
      return
    }

    if (e.key === 'Enter') {
      e.preventDefault()
      onVlozRadekPo(sekceIdx, radekIdx)
      zaostrBunku(sekceIdx, radekIdx + 1, 0, 0)
      return
    }

    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      const seznam = plochySeznamRadku()
      const tady = seznam.findIndex((r) => r.sekceIdx === sekceIdx && r.radekIdx === radekIdx)
      const cil = seznam[e.key === 'ArrowUp' ? tady - 1 : tady + 1]
      if (!cil) return
      const cilRadek = zapis.sekce[cil.sekceIdx].radky[cil.radekIdx]
      if (radekCelkemBunek(cilRadek) <= flatIdx) return
      e.preventDefault()
      focusFlatVRadku(cil.sekceIdx, cil.radekIdx, flatIdx)
    }
  }

  function naKlikBunky(e, sekceIdx, radekIdx, taktIdx, dobaIdx) {
    const radek = zapis.sekce[sekceIdx].radky[radekIdx]
    const bunkaIdxVRadku = flatIndexZPozice(radek, taktIdx, dobaIdx)
    const pozice = { sekceIdx, radekIdx, bunkaIdxVRadku }
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault()
      setVyber((prev) => prepniVeVyberu(prev, pozice))
      posledniKlikRef.current = pozice
      setRepeticeChyba(null)
    } else if (e.shiftKey && posledniKlikRef.current) {
      e.preventDefault()
      setVyber(rozsahMeziPozicemi(zapis, posledniKlikRef.current, pozice))
      setRepeticeChyba(null)
    } else {
      posledniKlikRef.current = pozice
    }
  }

  function otevriRepetici() {
    const kontrola = zkontrolujVyberProRepetici(zapis, vyber)
    if (!kontrola.ok) {
      setRepeticeChyba(kontrola.hlaska)
      return
    }
    setRepeticeChyba(null)
    setRepeticePopoverOtevreny(true)
  }

  function potvrdRepetici(krat) {
    const kontrola = zkontrolujVyberProRepetici(zapis, vyber)
    setRepeticePopoverOtevreny(false)
    if (!kontrola.ok) {
      setRepeticeChyba(kontrola.hlaska)
      return
    }
    onPridejRepetici(kontrola.sekceIdx, kontrola.od_taktu, kontrola.do_taktu, krat)
    setVyber([])
  }

  function potvrdZmenuTaktu(novyTakt) {
    const dobCil = novyTakt ? novyTakt.dob : zapis.takt.dob
    if (zpusobiZtratuZmenaVyberu(zapis, vyber, dobCil)) {
      if (
        !window.confirm(
          'Zúžení taktu zahodí obsah buněk, které se do nového počtu dob nevejdou. Pokračovat?',
        )
      ) {
        return
      }
    }
    onZmenTaktVyberu(vyber, novyTakt)
    setTaktPopoverOtevreny(false)
    setVyber([])
  }

  function smazatSekci(sekceIdx) {
    const sekce = zapis.sekce[sekceIdx]
    const neprazdna = sekce.radky.some((r) => r.takty.some((t) => t.bunky.some((b) => b)))
    if (neprazdna && !window.confirm(`Smazat sekci „${sekce.nazev || 'bez názvu'}“ i s obsahem?`)) {
      return
    }
    onSmazSekci(sekceIdx)
  }

  function pridatSekci() {
    const novyIndex = zapis.sekce.length
    onPridejSekci()
    zaostrNazevSekce(novyIndex)
  }

  const nejdelsi = nejdelsiRadekVDobach(zapis.sekce, zapis.takt)
  const cilDob = 4 * dob
  const infoRadek =
    nejdelsi > cilDob
      ? `Nejdelší řádek má ${nejdelsi} dob → PDF bude zmenšené na ${Math.round((cilDob / nejdelsi) * 100)} %.`
      : null

  return (
    <>
      {/* Skrytá sonda jen pro měření šířky buňky (viz efekt výš) — VŽDY
          přesně 4 takty výchozího taktu, nezávisle na skutečném obsahu
          zápisu (ten první takt/řádek klidně nemá). Neinteraktivní,
          mimo tab-pořadí, nulová výška — nezabírá místo, nevidí ji nikdo. */}
      <div className="akordy-mereni-sondy" aria-hidden="true">
        <div className="akordy-sekce-blok">
          <div className="akordy-radek">
            <div className="akordy-takty" ref={sondaRef}>
              {Array.from({ length: 4 }).map((_, taktIdx) => (
                <div key={taktIdx} className="akordy-takt">
                  <div className="akordy-takt-bunky">
                    {Array.from({ length: dob }).map((_, dobaIdx) => (
                      <input
                        key={dobaIdx}
                        type="text"
                        tabIndex={-1}
                        readOnly
                        value=""
                        className="akordy-bunka"
                        style={{ width: `${sirkaBunky}px` }}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="akordy-mrizka">
      {zapis.sekce.length === 0 && (
        <p className="akordy-prazdno">Zápis je zatím prázdný — přidej první sekci.</p>
      )}

      {zapis.sekce.map((sekce, sekceIdx) => (
        <div key={sekceIdx} className="akordy-sekce-blok">
          <div className="akordy-sekce-hlavicka">
            <input
              ref={(el) => {
                if (el) nazvySekciRef.current.set(sekceIdx, el)
                else nazvySekciRef.current.delete(sekceIdx)
              }}
              list="akordy-sekce-navrhy"
              className="field-input akordy-sekce-input"
              value={sekce.nazev}
              placeholder="Název sekce"
              onChange={(e) => onNastavNazevSekce(sekceIdx, e.target.value)}
              aria-label={`Název sekce ${sekceIdx + 1}`}
            />
            <button type="button" className="btn akordy-sekce-smazat" onClick={() => smazatSekci(sekceIdx)}>
              Smazat sekci
            </button>
          </div>

          <ul className="akordy-radky">
            {sekce.radky.map((radek, radekIdx) => (
              <li key={radekIdx} className="akordy-radek">
                <div className="akordy-takty">
                  {radek.takty.map((takt, taktIdx) => {
                    const efektivni = efektivniTakt(takt, zapis.takt)
                    return (
                      <div key={taktIdx} className="akordy-takt">
                        <div className="akordy-takt-hlavicka">
                          {takt.takt && (
                            <span className="akordy-takt-badge">
                              {efektivni.dob}/{efektivni.hodnota}
                            </span>
                          )}
                          <button
                            type="button"
                            className="akordy-takt-smazat"
                            onClick={() => onSmazTakt(sekceIdx, radekIdx, taktIdx)}
                            aria-label={`Smazat takt ${taktIdx + 1}`}
                            title="Smazat takt"
                          >
                            ×
                          </button>
                        </div>
                        <div className="akordy-takt-bunky">
                          {takt.bunky.map((text, dobaIdx) => (
                            <input
                              key={dobaIdx}
                              ref={refProBunku({ sekceIdx, radekIdx, taktIdx, dobaIdx })}
                              type="text"
                              style={{
                                width: `max(${sirkaBunky}px, calc(${Math.max(text.length, 1) + 1}ch + var(--space-3)))`,
                              }}
                              className={`akordy-bunka${
                                vyberObsahuje(vyber, {
                                  sekceIdx,
                                  radekIdx,
                                  bunkaIdxVRadku: flatIndexZPozice(radek, taktIdx, dobaIdx),
                                })
                                  ? ' akordy-bunka-vybrana'
                                  : ''
                              }`}
                              value={text}
                              autoCorrect="off"
                              autoCapitalize="off"
                              spellCheck={false}
                              onChange={(e) => onUpravBunku(sekceIdx, radekIdx, taktIdx, dobaIdx, e.target.value)}
                              onKeyDown={(e) => naKlavesu(e, sekceIdx, radekIdx, taktIdx, dobaIdx)}
                              onClick={(e) => naKlikBunky(e, sekceIdx, radekIdx, taktIdx, dobaIdx)}
                              aria-label={`Doba ${dobaIdx + 1}, takt ${taktIdx + 1}, řádek ${radekIdx + 1}, sekce ${sekceIdx + 1}`}
                            />
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </li>
            ))}
          </ul>

          {sekce.repetice.length > 0 && (
            <ul className="akordy-repetice-seznam" aria-label={`Repetice sekce ${sekceIdx + 1}`}>
              {sekce.repetice.map((rep, repIdx) => (
                <li key={repIdx}>
                  <button
                    type="button"
                    className="akordy-repetice-chip"
                    onClick={() => onSmazRepetici(sekceIdx, repIdx)}
                    title="Klikem odebrat"
                  >
                    takt {rep.od_taktu + 1}–{rep.do_taktu + 1} ×{rep.krat} ✕
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}

      <datalist id="akordy-sekce-navrhy">
        {SEKCE_NAVRHY.map((s) => (
          <option key={s} value={s} />
        ))}
      </datalist>

      <div className="akordy-mrizka-akce">
        <button type="button" className="btn btn-secondary" onClick={pridatSekci}>
          + Přidat sekci
        </button>
        {vyber.length > 0 && (
          <div className="akordy-vyber-akce">
            <span className="akordy-vyber-info">{vyber.length} vybraných buněk</span>
            <button type="button" className="btn btn-secondary" onClick={otevriRepetici}>
              Repetice
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setTaktPopoverOtevreny(true)}>
              Změnit takt
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
      {infoRadek && <p className="akordy-info-radek">{infoRadek}</p>}

      {repeticePopoverOtevreny && (
        <RepeticePopover onPotvrdit={potvrdRepetici} onZrusit={() => setRepeticePopoverOtevreny(false)} />
      )}
      {taktPopoverOtevreny && (
        <ZmenitTaktPopover onPotvrdit={potvrdZmenuTaktu} onZrusit={() => setTaktPopoverOtevreny(false)} />
      )}
      </div>
    </>
  )
}
