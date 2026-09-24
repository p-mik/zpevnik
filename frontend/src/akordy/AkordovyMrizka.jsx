import { useEffect, useRef, useState } from 'react'
import {
  SEKCE_NAVRHY,
  efektivniTakt,
  flatIndexZPozice,
  nejdelsiRadekVDobach,
  poziceVRadku,
  prepniVeVyberu,
  radekCelkemBunek,
  rozdelRadekOdTaktu,
  rozdelSekciOdRadku,
  rozsahMeziPozicemi,
  vyberObsahuje,
  voltyVRadku,
  zkontrolujVyberProRepetici,
  zkontrolujVyberProVoltu,
  zpusobiZtratuZmenaVyberu,
} from './akordovyModel'
import RepeticePopover from './RepeticePopover'
import VoltaPopover from './VoltaPopover'
import ZmenitTaktPopover from './ZmenitTaktPopover'
import './AkordovyMrizka.css'

const MIN_SIRKA_BUNKY = 36
// Cíl šířky buňky NENÍ "přesně 4 takty na šířku" — je to vědomá rezerva
// (viz zadání): 4 takty výchozího taktu musí mít po pravé straně ještě
// viditelné místo, ne sedět na hraně. Počítáno tak, aby se teoreticky
// vešlo 4,5 taktu — ta rezerva pak vstřebá jak zaokrouhlení/scrollbar, tak
// akordy, které si (přes `max(základ, šířka textu)`, viz .akordy-bunka)
// vynutí širší buňku, než je základ (např. "Eadd9").
const CIL_TAKTU_PRO_SIRKU = 4.5

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
  const [sirkaBunky, setSirkaBunky] = useState(64)
  const sondaRef = useRef(null)

  // Šířka buňky: 4 takty výchozího taktu musí mít po pravé straně viditelnou
  // rezervu (viz CIL_TAKTU_PRO_SIRKU výš), ne sedět přesně na hraně
  // kontejneru. Hrubý odhad (šířka sloupce / počet dob) nepočítá s
  // mezerami mezi buňkami, oddělovači taktů (border-left), paddingem
  // taktů, ani s tlačítkem "Nová sekce od tohoto řádku" (to u řádků > 0
  // ubírá další místo) — proto se koriguje přeměřením: rozdíl mezi
  // skutečně vykresleným scrollWidth sondy a odhadem*počet_dob je ta
  // "režie", která NEZÁVISÍ na šířce buňky, takže jedna korekce z reálně
  // vykreslené šířky buňky stačí. Sonda proto nese i (skryté) tlačítko
  // rozdělení — nejhorší případ, ať se z něj nevypočítá málo místa pro
  // řádky, které ho skutečně mají. Pod MIN_SIRKA_BUNKY je scroll povolený.
  useEffect(() => {
    const el = sondaRef.current
    if (!el) return undefined
    function prepocitej() {
      const celkemDob = CIL_TAKTU_PRO_SIRKU * dob
      if (celkemDob <= 0) return
      const prvniBunka = el.querySelector('.akordy-bunka')
      const aktualniSirkaBunky = prvniBunka
        ? prvniBunka.getBoundingClientRect().width
        : el.clientWidth / (4 * dob)
      // Sonda sama vykresluje jen 4 (ne 4,5) taktu — to, co se skutečně
      // renderuje, i co určuje overhead (mezery, oddělovače, tlačítko).
      const rezie = el.scrollWidth - 4 * dob * aktualniSirkaBunky
      const presna = Math.max(MIN_SIRKA_BUNKY, (el.clientWidth - rezie) / celkemDob)
      setSirkaBunky(presna)
    }
    prepocitej()
    const ro = new ResizeObserver(prepocitej)
    ro.observe(el)
    // Pojistka pro případ, že by CSS/fonty dorazily až po prvním layoutu
    // — i bez vlastního webfontu se může první měření strefit do okna, kdy
    // prohlížeč ještě nemá layout/fonty definitivně ustálené.
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
      {/* Panel akcí (PC_zpevnik_akordy_ovladani.md bod 6) — fixní u levého
          okraje OKNA (ne sekce/stránky), svisle na střed, drží se při
          scrollování. Akce závislé na výběru (Repetice/Volta/Změnit takt)
          jsou bez výběru NEAKTIVNÍ, ne skryté — zadání to chce takhle
          schválně, ať je panel vždycky na stejném místě se stejným
          obsahem, žádné poskakování layoutu podle toho, jestli je něco
          vybrané. ".akordy-mrizka-obsah" níž dostává odpovídající
          odsazení zleva, ať se panel nepřekrývá s mřížkou. */}
      <div className="akordy-panel-akci" role="toolbar" aria-label="Akce akordového zápisu">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={otevriRepetici}
          disabled={vyber.length === 0}
        >
          Repetice
        </button>
        <button type="button" className="btn btn-secondary" onClick={otevriVoltu} disabled={vyber.length === 0}>
          Volta
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => setTaktPopoverOtevreny(true)}
          disabled={vyber.length === 0}
        >
          Změnit takt
        </button>
        <button type="button" className="btn btn-secondary" onClick={pridatSekci}>
          + Přidat sekci
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={pridatSekciBezRadku}
          title="Sekce jen s nadpisem, bez taktů — třeba „Sloka 2 = Sloka 1“."
        >
          + Jen nadpis
        </button>
        <p className="akordy-panel-napoveda">
          <strong>Tab</strong> další buňka
          <br />
          <strong>Enter</strong> nový řádek
          <br />
          <strong>Backspace</strong> spojí s předchozím
        </p>
      </div>

      <div className="akordy-mrizka-vyskok">
      <div className="akordy-mrizka-obsah">
      {/* Skrytá sonda jen pro měření šířky buňky (viz efekt výš) — VŽDY
          přesně 4 takty výchozího taktu (+ tlačítko rozdělení, nejhorší
          případ), nezávisle na skutečném obsahu zápisu. Neinteraktivní,
          mimo tab-pořadí, nulová výška — nezabírá místo, nevidí ji nikdo. */}
      <div className="akordy-mereni-sondy" aria-hidden="true">
        <div className="akordy-sekce-blok">
          <div className="akordy-sekce-scroll">
            <ul className="akordy-radky">
              <li className="akordy-radek" ref={sondaRef}>
                <div className="akordy-takty">
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
                <button type="button" className="akordy-radek-rozdelit" tabIndex={-1}>
                  ✂ Nová sekce od tohoto řádku
                </button>
              </li>
            </ul>
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
              <div className="akordy-sekce-presun">
                {sekceIdx > 0 && (
                  <button
                    type="button"
                    className="btn akordy-sekce-sipka"
                    onClick={() => onPosunSekci(sekceIdx, -1)}
                    aria-label="Posunout sekci nahoru"
                    title="Posunout sekci nahoru"
                  >
                    ↑
                  </button>
                )}
                {sekceIdx < zapis.sekce.length - 1 && (
                  <button
                    type="button"
                    className="btn akordy-sekce-sipka"
                    onClick={() => onPosunSekci(sekceIdx, 1)}
                    aria-label="Posunout sekci dolů"
                    title="Posunout sekci dolů"
                  >
                    ↓
                  </button>
                )}
              </div>
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
              {sekceIdx > 0 && (
                <button
                  type="button"
                  className="btn akordy-sekce-spojit"
                  onClick={() => spojit(sekceIdx)}
                  title="Spojí tuhle sekci s předchozí — název téhle se zahodí."
                >
                  Spojit s předchozí
                </button>
              )}
              <button
                type="button"
                className="btn akordy-sekce-duplikovat"
                onClick={() => duplikovat(sekceIdx)}
                title="Vloží kopii téhle sekce hned pod ni."
              >
                Duplikovat
              </button>
              <button type="button" className="btn akordy-sekce-smazat" onClick={() => smazatSekci(sekceIdx)}>
                Smazat sekci
              </button>
            </div>

            {sekce.radky.length === 0 ? (
              // Sekce jen s nadpisem, bez taktů (viz schéma bod "radky
              // smí být prázdné") — smazáním úplně posledního taktu sem
              // sekce dojde sama (viz odeberTaktZeSekce), zpátky na
              // obsah vede jen tenhle jeden krok. `-1` = vlož na začátek
              // (vlozRadekPo počítá "po radekIdx", -1 je "před vším").
              <button
                type="button"
                className="btn btn-secondary akordy-radek-pridat"
                onClick={() => onVlozRadekPo(sekceIdx, -1)}
              >
                + Přidat řádek
              </button>
            ) : (
            <div className="akordy-sekce-scroll">
              <ul className="akordy-radky">
                {sekce.radky.map((radek, radekIdx) => {
                  const voltySeznam = voltyVRadku(sekce, radekIdx)
                  const voltaProTakt = (taktIdx) =>
                    voltySeznam.find((v) => taktIdx >= v.odTaktLokalni && taktIdx <= v.doTaktLokalni)
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
                        return (
                          <div key={taktIdx} className="akordy-takt">
                            {voltaTady && (
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
                            )}
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
                    {radekIdx > 0 && (
                      <button
                        type="button"
                        className="akordy-radek-rozdelit"
                        onClick={() => rozdelit(sekceIdx, radekIdx)}
                      >
                        ✂ Nová sekce od tohoto řádku
                      </button>
                    )}
                  </li>
                  )
                })}
              </ul>
            </div>
            )}

            {chybaRozdeleni && chybaRozdeleni.sekceIdx === sekceIdx && (
              <p className="akordy-repetice-chyba" role="alert">
                {chybaRozdeleni.hlaska}
              </p>
            )}

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
