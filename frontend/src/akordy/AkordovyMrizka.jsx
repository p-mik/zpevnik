import { useEffect, useRef, useState } from 'react'
import {
  SEKCE_NAVRHY,
  efektivniTakt,
  flatIndexZPozice,
  nejdelsiRadekVDobach,
  pocetTaktuVSekci,
  poziceVRadku,
  prepniVeVyberu,
  radekCelkemBunek,
  repeticeVRadku,
  rozdelRadekOdTaktu,
  rozdelSekciOdRadku,
  rozsahMeziPozicemi,
  vyberObsahuje,
  voltyVRadku,
  zkontrolujVyberProRepetici,
  zkontrolujVyberProVoltu,
  zpusobiZtratuZmenaVyberu,
} from './akordovyModel'
import {
  IkonaDolu,
  IkonaDuplikovat,
  IkonaKrizek,
  IkonaNahoru,
  IkonaNuzky,
  IkonaPlus,
  IkonaSmazat,
  IkonaSpojitSPredchozi,
} from './AkordyIkony'
import AkordovyToolbar from './AkordovyToolbar'
import RepeticePopover from './RepeticePopover'
import VoltaPopover from './VoltaPopover'
import ZmenitTaktPopover from './ZmenitTaktPopover'
import './AkordovyMrizka.css'

const NAZEV_SEKCE_PLACEHOLDER = 'Název sekce'

// Skloňování "takt" — 1 takt, 2-4 takty, 0 a 5+ taktů (viz zadání bod 3,
// meta info v hlavičce sekce).
function metaSekce(sekce) {
  const pocet = pocetTaktuVSekci(sekce)
  if (pocet === 0) return 'prázdná'
  if (pocet === 1) return '1 takt'
  if (pocet <= 4) return `${pocet} takty`
  return `${pocet} taktů`
}

// Mřížka akordového zápisu — sekce jsou bloky (jméno jednou nahoře, pod
// ním řádky taktů), viz PC_zpevnik_akordovy_zapis_upravy.md bod 1. ŘÁDEK
// SE NIKDY SÁM NEZALAMUJE (bod 4) — delší řádek prostě odscrolluje
// vodorovně, PDF ho zmenší jako celek (viz info hláška dole). Scroll je
// SDÍLENÝ pro celou sekci (viz .akordy-sekce-scroll) — všechny řádky
// jedné sekce se posouvají spolu, ne každý zvlášť.
//
// Klávesy:
//  Tab        další buňka; na konci řádku přidá nový takt a skočí do něj
//  Shift+Tab  předchozí buňka; přes hranici řádku (i sekce) do konce předchozího
//  Enter      zalomí řádek ZA taktem, kde stojí kurzor — takty za ním se
//             přesunou na nový řádek pod ním, ve STEJNÉ sekci. Když je
//             kurzor v POSLEDNÍM taktu řádku, jednoduše založí nový
//             prázdný řádek pod ním (zalomení by nemělo co přesouvat).
//             Repetice přes místo zalomení: odmítnuto se stejnou hláškou
//             jako u dělení sekce.
//  Backspace  v PRVNÍ (prázdné) buňce řádku spojí takty řádku na konec
//             PŘEDCHOZÍHO řádku téže sekce, řádek zmizí, kurzor zůstane
//             na stejné (teď přesunuté) buňce. První řádek sekce: nic
//             (hranice sekcí se nespojuje). Jinak maže text jako obvykle.
//  ↑ / ↓      stejná pozice v řádku nad/pod (napříč celým zápisem), jen
//             když tam buňka existuje
export default function AkordovyMrizka({
  zapis,
  onUpravBunku,
  onNastavNazevSekce,
  onPridejTakt,
  onSmazTakt,
  onVlozRadekPo,
  onRozdelRadek,
  onSpojRadek,
  onSmazSekci,
  onPridejSekci,
  onPridejSekciBezRadku,
  onRozdelSekci,
  onSpojSePredchozi,
  onPosunSekci,
  onDuplikujSekci,
  onPridejRepetici,
  onSmazRepetici,
  onPridejVoltu,
  onSmazVoltu,
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
  const [voltaPopoverOtevreny, setVoltaPopoverOtevreny] = useState(false)
  const [taktPopoverOtevreny, setTaktPopoverOtevreny] = useState(false)
  const [chybaRozdeleni, setChybaRozdeleni] = useState(null)

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
      const jePosledniTaktRadku = taktIdx === radek.takty.length - 1
      if (jePosledniTaktRadku) {
        onVlozRadekPo(sekceIdx, radekIdx)
        zaostrBunku(sekceIdx, radekIdx + 1, 0, 0)
        return
      }
      // Zalomení validujeme TADY (čistá funkce nad aktuálním zápisem,
      // stejný vzor jako "Nová sekce od tohoto řádku") — akce v
      // useAkordovyEditor pak jen aplikuje.
      const vysledek = rozdelRadekOdTaktu(zapis.sekce[sekceIdx], radekIdx, taktIdx + 1)
      if (!vysledek.ok) {
        setChybaRozdeleni({ sekceIdx, hlaska: vysledek.hlaska })
        return
      }
      setChybaRozdeleni(null)
      onRozdelRadek(sekceIdx, radekIdx, taktIdx + 1)
      zaostrBunku(sekceIdx, radekIdx, taktIdx, dobaIdx)
      return
    }

    if (e.key === 'Backspace') {
      // Jen v PRVNÍ (flatIdx 0) buňce řádku, kterou je PRÁZDNÁ, a jen
      // když je co spojit (ne první řádek sekce — hranice sekcí se
      // nespojuje). Jinak Backspace maže text jako obvykle — nic se tu
      // nedělá, žádný preventDefault.
      if (flatIdx === 0 && !e.target.value && radekIdx > 0) {
        e.preventDefault()
        const predchoziRadek = zapis.sekce[sekceIdx].radky[radekIdx - 1]
        const noveTaktIdx = predchoziRadek.takty.length
        onSpojRadek(sekceIdx, radekIdx)
        zaostrBunku(sekceIdx, radekIdx - 1, noveTaktIdx, 0)
      }
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

  function otevriVoltu() {
    const kontrola = zkontrolujVyberProVoltu(zapis, vyber)
    if (!kontrola.ok) {
      setRepeticeChyba(kontrola.hlaska)
      return
    }
    setRepeticeChyba(null)
    setVoltaPopoverOtevreny(true)
  }

  function potvrdVoltu(cislo) {
    const kontrola = zkontrolujVyberProVoltu(zapis, vyber)
    setVoltaPopoverOtevreny(false)
    if (!kontrola.ok) {
      setRepeticeChyba(kontrola.hlaska)
      return
    }
    onPridejVoltu(kontrola.sekceIdx, kontrola.od_taktu, kontrola.do_taktu, cislo)
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

  function pridatSekciBezRadku() {
    const novyIndex = zapis.sekce.length
    onPridejSekciBezRadku()
    zaostrNazevSekce(novyIndex)
  }

  // Rozdělení se validuje TADY (čistá funkce nad aktuálním zápisem, stejný
  // vzor jako potvrzení "Změnit takt") — akce v useAkordovyEditor pak jen
  // aplikuje, beze změny se stará jen o no-op, kdyby se sem přesto dostal
  // neplatný požadavek.
  function rozdelit(sekceIdx, radekIdx) {
    const vysledek = rozdelSekciOdRadku(zapis.sekce[sekceIdx], radekIdx)
    if (!vysledek.ok) {
      setChybaRozdeleni({ sekceIdx, hlaska: vysledek.hlaska })
      return
    }
    setChybaRozdeleni(null)
    onRozdelSekci(sekceIdx, radekIdx)
    zaostrNazevSekce(sekceIdx + 1)
  }

  function spojit(sekceIdx) {
    setChybaRozdeleni(null)
    onSpojSePredchozi(sekceIdx)
  }

  function duplikovat(sekceIdx) {
    onDuplikujSekci(sekceIdx)
    zaostrNazevSekce(sekceIdx + 1)
  }

  const nejdelsi = nejdelsiRadekVDobach(zapis.sekce, zapis.takt)
  const cilDob = 4 * dob
  const infoRadek =
    nejdelsi > cilDob
      ? `Nejdelší řádek má ${nejdelsi} dob → PDF bude zmenšené na ${Math.round((cilDob / nejdelsi) * 100)} %.`
      : null

  return (
    <>
      <AkordovyToolbar
        vyberAktivni={vyber.length > 0}
        onRepetice={otevriRepetici}
        onVolta={otevriVoltu}
        onTakt={() => setTaktPopoverOtevreny(true)}
        onPridejSekci={pridatSekci}
        onPridejSekciBezRadku={pridatSekciBezRadku}
      />

      <div className="akordy-mrizka-vyskok">
      <div className="akordy-mrizka-obsah">

      <div className="akordy-mrizka">
        {zapis.sekce.length === 0 && (
          <p className="akordy-prazdno">Zápis je zatím prázdný — přidej první sekci.</p>
        )}

        {zapis.sekce.map((sekce, sekceIdx) => {
          const jePrvni = sekceIdx === 0
          const jePosledni = sekceIdx === zapis.sekce.length - 1

          if (sekce.radky.length === 0) {
            // "Nadpis" (docs/zadani_redesign_akordovy_zapis.md bod 3,
            // poslední odrážka) — POZOR: `radky: []` v datech vzniká DVOJÍM
            // způsobem, appka mezi nimi nerozlišuje (jedno pole, žádný nový
            // příznak — zadání výslovně zakazuje měnit data): buď záměrně
            // (toolbar "Nadpis"), nebo smazáním úplně posledního taktu
            // normální sekce (viz odeberTaktZeSekce). Obě cesty proto
            // dostávají STEJNÝ štíhlý vzhled bez boxu. Zadání pro "Nadpis"
            // popisuje jen šipky+název+linku+smazání, ale současná appka umí
            // pro tenhle stav i "Spojit s předchozí"/"Duplikovat"/založit
            // první řádek (dřívější "+ Přidat řádek") — jejich smazání by
            // byl regres funkčnosti, ne jen vzhledu, takže zůstávají, jen
            // zaskládané za linku jako malé ikony/odkaz.
            return (
              <div key={sekceIdx} className="akordy-nadpis-radek">
                <div className="akordy-sekce-presun">
                  {!jePrvni && (
                    <button
                      type="button"
                      className="akordy-ikona-btn akordy-ikona-btn-presun"
                      onClick={() => onPosunSekci(sekceIdx, -1)}
                      aria-label="Posunout sekci nahoru"
                      title="Posunout sekci nahoru"
                    >
                      <IkonaNahoru size={10} />
                    </button>
                  )}
                  {!jePosledni && (
                    <button
                      type="button"
                      className="akordy-ikona-btn akordy-ikona-btn-presun"
                      onClick={() => onPosunSekci(sekceIdx, 1)}
                      aria-label="Posunout sekci dolů"
                      title="Posunout sekci dolů"
                    >
                      <IkonaDolu size={10} />
                    </button>
                  )}
                </div>
                <input
                  ref={(el) => {
                    if (el) nazvySekciRef.current.set(sekceIdx, el)
                    else nazvySekciRef.current.delete(sekceIdx)
                  }}
                  list="akordy-sekce-navrhy"
                  className="akordy-nazev-input akordy-nadpis-nazev"
                  value={sekce.nazev}
                  placeholder={NAZEV_SEKCE_PLACEHOLDER}
                  onChange={(e) => onNastavNazevSekce(sekceIdx, e.target.value)}
                  aria-label={`Název sekce ${sekceIdx + 1}`}
                />
                <span className="akordy-nadpis-linka" aria-hidden="true" />
                <button
                  type="button"
                  className="akordy-radek-pridat-male"
                  onClick={() => onVlozRadekPo(sekceIdx, -1)}
                >
                  <IkonaPlus size={11} />
                  řádek
                </button>
                {!jePrvni && (
                  <button
                    type="button"
                    className="akordy-ikona-btn"
                    onClick={() => spojit(sekceIdx)}
                    aria-label="Spojit s předchozí"
                    title="Spojí tuhle sekci s předchozí — název téhle se zahodí."
                  >
                    <IkonaSpojitSPredchozi size={15} />
                  </button>
                )}
                <button
                  type="button"
                  className="akordy-ikona-btn"
                  onClick={() => duplikovat(sekceIdx)}
                  aria-label="Duplikovat"
                  title="Vloží kopii téhle sekce hned pod ni."
                >
                  <IkonaDuplikovat size={15} />
                </button>
                <button
                  type="button"
                  className="akordy-ikona-btn akordy-ikona-btn-nebezpecna"
                  onClick={() => smazatSekci(sekceIdx)}
                  aria-label="Smazat nadpis"
                  title="Smazat sekci"
                >
                  <IkonaSmazat size={15} />
                </button>
              </div>
            )
          }

          return (
          <div key={sekceIdx} className="akordy-sekce-blok">
            <div className="akordy-sekce-hlavicka">
              <div className="akordy-sekce-presun">
                {!jePrvni && (
                  <button
                    type="button"
                    className="akordy-ikona-btn akordy-ikona-btn-presun"
                    onClick={() => onPosunSekci(sekceIdx, -1)}
                    aria-label="Posunout sekci nahoru"
                    title="Posunout sekci nahoru"
                  >
                    <IkonaNahoru size={10} />
                  </button>
                )}
                {!jePosledni && (
                  <button
                    type="button"
                    className="akordy-ikona-btn akordy-ikona-btn-presun"
                    onClick={() => onPosunSekci(sekceIdx, 1)}
                    aria-label="Posunout sekci dolů"
                    title="Posunout sekci dolů"
                  >
                    <IkonaDolu size={10} />
                  </button>
                )}
              </div>
              <input
                ref={(el) => {
                  if (el) nazvySekciRef.current.set(sekceIdx, el)
                  else nazvySekciRef.current.delete(sekceIdx)
                }}
                list="akordy-sekce-navrhy"
                className="akordy-nazev-input akordy-sekce-nazev"
                value={sekce.nazev}
                placeholder={NAZEV_SEKCE_PLACEHOLDER}
                onChange={(e) => onNastavNazevSekce(sekceIdx, e.target.value)}
                aria-label={`Název sekce ${sekceIdx + 1}`}
              />
              <span className="akordy-sekce-meta">{metaSekce(sekce)}</span>
              {sekce.repetice.map((rep, repIdx) => (
                <span key={repIdx} className="akordy-sekce-badge-repetice">
                  {rep.od_taktu + 1}–{rep.do_taktu + 1} ×{rep.krat}
                  <button
                    type="button"
                    className="akordy-sekce-badge-smazat"
                    onClick={() => onSmazRepetici(sekceIdx, repIdx)}
                    aria-label="Zrušit repetici"
                    title="Zrušit repetici"
                  >
                    <IkonaKrizek size={10} />
                  </button>
                </span>
              ))}
              <div className="akordy-sekce-mezera" />
              {!jePrvni && (
                <button
                  type="button"
                  className="akordy-ikona-btn"
                  onClick={() => spojit(sekceIdx)}
                  aria-label="Spojit s předchozí"
                  title="Spojí tuhle sekci s předchozí — název téhle se zahodí."
                >
                  <IkonaSpojitSPredchozi size={15} />
                </button>
              )}
              <button
                type="button"
                className="akordy-ikona-btn"
                onClick={() => duplikovat(sekceIdx)}
                aria-label="Duplikovat"
                title="Vloží kopii téhle sekce hned pod ni."
              >
                <IkonaDuplikovat size={15} />
              </button>
              <button
                type="button"
                className="akordy-ikona-btn akordy-ikona-btn-nebezpecna"
                onClick={() => smazatSekci(sekceIdx)}
                aria-label="Smazat sekci"
                title="Smazat sekci"
              >
                <IkonaSmazat size={15} />
              </button>
            </div>

            <div className="akordy-sekce-telo">
            <div className="akordy-sekce-scroll">
              <ul className="akordy-radky">
                {sekce.radky.map((radek, radekIdx) => {
                  const voltySeznam = voltyVRadku(sekce, radekIdx)
                  const voltaProTakt = (taktIdx) =>
                    voltySeznam.find((v) => taktIdx >= v.odTaktLokalni && taktIdx <= v.doTaktLokalni)
                  const repeticeSeznam = repeticeVRadku(sekce, radekIdx)
                  const repeticeProTakt = (taktIdx) =>
                    repeticeSeznam.find((r) => taktIdx >= r.odTaktLokalni && taktIdx <= r.doTaktLokalni)
                  const posledniTaktIdx = radek.takty.length - 1
                  return (
                  <li key={radekIdx} className="akordy-radek">
                    <div className="akordy-takty">
                      {radek.takty.map((takt, taktIdx) => {
                        const efektivni = efektivniTakt(takt, zapis.takt)
                        const voltaTady = voltaProTakt(taktIdx)
                        const jeZacatekVoltyVRadku =
                          voltaTady && taktIdx === voltaTady.odTaktLokalni && voltaTady.kresliZacatek
                        const jeKonecVoltyVRadku =
                          voltaTady && taktIdx === voltaTady.doTaktLokalni && voltaTady.kresliKonec
                        const repeticeTady = repeticeProTakt(taktIdx)
                        const jeZacatekRepeticeVRadku =
                          repeticeTady && taktIdx === repeticeTady.odTaktLokalni && repeticeTady.kresliZacatek
                        const jeKonecRepeticeVRadku =
                          repeticeTady && taktIdx === repeticeTady.doTaktLokalni && repeticeTady.kresliKonec
                        return (
                          <div key={taktIdx} className="akordy-takt">
                            {/* Pruh nad taktem (bod 4) — rezervovaný u VŠECH
                                taktů (i bez volty), ať řádky nelítají podle
                                toho, jestli zrovna nějaká volta je. Vlastní
                                takt (badge N/M) se do něj vejde, jen když tam
                                zrovna není volta — souběh obojího na jednom
                                taktu je natolik vzácný okrajový případ, že
                                zadání ho neřeší a volta má přednost. */}
                            <div className="akordy-takt-pruh">
                              {voltaTady ? (
                                <button
                                  type="button"
                                  className={`akordy-volta-segment${jeZacatekVoltyVRadku ? ' akordy-volta-zacatek' : ''}${
                                    jeKonecVoltyVRadku && voltaTady.volta.cislo !== 1 ? ' akordy-volta-konec-uzavrena' : ''
                                  }`}
                                  onClick={() => onSmazVoltu(sekceIdx, voltaTady.voltaIdx)}
                                  title={`Volta ${voltaTady.volta.cislo} — kliknutím smazat`}
                                >
                                  {jeZacatekVoltyVRadku && (
                                    <span className="akordy-volta-cislo">{voltaTady.volta.cislo}.</span>
                                  )}
                                </button>
                              ) : (
                                takt.takt && (
                                  <span className="akordy-takt-badge">
                                    {efektivni.dob}/{efektivni.hodnota}
                                  </span>
                                )
                              )}
                            </div>
                            <div className="akordy-takt-beat-radek">
                              {jeZacatekRepeticeVRadku && (
                                <span className="akordy-repetice-znacka akordy-repetice-znacka-zacatek" aria-hidden="true">
                                  <span className="akordy-repetice-cara" />
                                  <span className="akordy-repetice-tecky">
                                    <span className="akordy-repetice-tecka" />
                                    <span className="akordy-repetice-tecka" />
                                  </span>
                                </span>
                              )}
                              <div
                                className="akordy-takt-bunky"
                                style={{ gridTemplateColumns: `repeat(${takt.bunky.length}, minmax(max-content, 1fr))` }}
                              >
                                {takt.bunky.map((text, dobaIdx) => (
                                  <input
                                    key={dobaIdx}
                                    ref={refProBunku({ sekceIdx, radekIdx, taktIdx, dobaIdx })}
                                    type="text"
                                    placeholder=" "
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
                              {jeKonecRepeticeVRadku && (
                                <span className="akordy-repetice-znacka akordy-repetice-znacka-konec" aria-hidden="true">
                                  <span className="akordy-repetice-tecky">
                                    <span className="akordy-repetice-tecka" />
                                    <span className="akordy-repetice-tecka" />
                                  </span>
                                  <span className="akordy-repetice-cara" />
                                </span>
                              )}
                              {taktIdx === posledniTaktIdx && (
                                <span className="akordy-takt-zaviraci-cara" aria-hidden="true" />
                              )}
                            </div>
                            <button
                              type="button"
                              className="akordy-takt-smazat"
                              onClick={() => onSmazTakt(sekceIdx, radekIdx, taktIdx)}
                              aria-label={`Smazat takt ${taktIdx + 1}`}
                              title="Smazat takt"
                            >
                              <IkonaKrizek size={10} />
                            </button>
                          </div>
                        )
                      })}
                    </div>
                    {radekIdx > 0 && (
                      <button
                        type="button"
                        className="akordy-radek-rozdelit"
                        onClick={() => rozdelit(sekceIdx, radekIdx)}
                        aria-label="Nová sekce od tohoto řádku"
                        title="Nová sekce od tohoto řádku"
                      >
                        <IkonaNuzky size={15} />
                      </button>
                    )}
                  </li>
                  )
                })}
              </ul>
            </div>
            <button
              type="button"
              className="akordy-radek-pridat-male"
              onClick={() => onVlozRadekPo(sekceIdx, sekce.radky.length - 1)}
            >
              <IkonaPlus size={11} />
              řádek
            </button>
            </div>

            {chybaRozdeleni && chybaRozdeleni.sekceIdx === sekceIdx && (
              <p className="akordy-repetice-chyba" role="alert">
                {chybaRozdeleni.hlaska}
              </p>
            )}
          </div>
          )
        })}

        <datalist id="akordy-sekce-navrhy">
          {SEKCE_NAVRHY.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>

        {vyber.length > 0 && (
          <div className="akordy-vyber-akce">
            <span className="akordy-vyber-info">{vyber.length} vybraných buněk</span>
            <button type="button" className="btn akordy-vyber-zrusit" onClick={() => setVyber([])}>
              Zrušit výběr
            </button>
          </div>
        )}

        {repeticeChyba && (
          <p className="akordy-repetice-chyba" role="alert">
            {repeticeChyba}
          </p>
        )}
        {infoRadek && <p className="akordy-info-radek">{infoRadek}</p>}

        {repeticePopoverOtevreny && (
          <RepeticePopover onPotvrdit={potvrdRepetici} onZrusit={() => setRepeticePopoverOtevreny(false)} />
        )}
        {voltaPopoverOtevreny && (
          <VoltaPopover onPotvrdit={potvrdVoltu} onZrusit={() => setVoltaPopoverOtevreny(false)} />
        )}
        {taktPopoverOtevreny && (
          <ZmenitTaktPopover onPotvrdit={potvrdZmenuTaktu} onZrusit={() => setTaktPopoverOtevreny(false)} />
        )}
      </div>
      </div>
      </div>
    </>
  )
}
