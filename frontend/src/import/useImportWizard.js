import { useCallback, useMemo, useRef, useState } from 'react'
import pdfjsLib from '../pdf/pdfjs'
import { useAllPages } from '../hooks/useAllPages'
import { parseAllPages } from './parsePdfPages'
import { groupPagesIntoSongs, analyzeProblems, planJeValidni } from './planAnalysis'
import { navrhniNazvyKategorii, buildKategorieState } from './deriveKategorie'
import { prirazKody, dalsiVolnaStovka } from './kodyAuto'
import { submitImport } from './submitImport'
import { extractErrorMessage } from '../api/errors'

const CHYBA_IMPORTU = 'Import se nepodařilo provést.'

// `presetZpevnikId` — když se import spustí Z KONKRÉTNÍHO zpěvníku (viz
// SongbookPage "+ Import PDF"), cíl je předvyplněný a napevno "existující",
// ať uživatel nemusí zpěvník hledat znovu ve výběru.
const prazdnyCil = (presetZpevnikId) =>
  presetZpevnikId
    ? { mod: 'existujici', nazev: '', existujiciId: String(presetZpevnikId) }
    : { mod: 'novy', nazev: '', existujiciId: '' }

// STEP: 'upload' -> 'parsing' -> 'review' -> 'kategorie' -> 'submitting' -> 'result'
export function useImportWizard(presetZpevnikId) {
  const [step, setStep] = useState('upload')
  const [fileName, setFileName] = useState('')
  const [pages, setPages] = useState([])
  const [kategorie, setKategorie] = useState([])
  // Textově, ne rovnou číslo — pole musí umět být prázdné (= dopočítej sám,
  // viz kodyAuto.js), a to "0" ani "" jako Number nejde rozlišit dobře.
  const [kodyOdText, setKodyOdText] = useState('')
  // Cíl importu (PC_zpevnik_sprava.md bod 4) — POVINNÝ, nezávislý na
  // kategoriích níž (kategorie jsou jen pro procházení, cíl je "ta kniha
  // jako celek", na kterou má smysl navázat setlist/QR odkaz). `mod: 'novy'`
  // založí nový zpěvník podle `nazev` (předvyplněný z názvu souboru),
  // `mod: 'existujici'` zařadí do zpěvníku vybraného podle `existujiciId`.
  const [celyZpevnik, setCelyZpevnik] = useState(() => prazdnyCil(presetZpevnikId))
  const [parseProgress, setParseProgress] = useState({ done: 0, total: 0 })
  const [parseError, setParseError] = useState(null)
  const [submitError, setSubmitError] = useState(null)
  const [result, setResult] = useState(null)

  const fileRef = useRef(null)
  const pdfDocRef = useRef(null)
  const objectUrlRef = useRef(null)
  // Jména kategorií odvozená z obsahové stránky při parsování — kategorie se
  // (kvůli kódům dopočítaným až z "Kódy od") přestavují znovu při přechodu na
  // krok Kategorie, tohle je zase nemusí pokaždé přeparsovávat z PDF.
  const kategorieLabelsRef = useRef(new Map())

  // Existující kódy — pro warning v tabulce ("duplicitní-kod-db") a pro
  // výchozí "Kódy od". Autoritativní kontrolu stejně dělá až server při
  // potvrzení importu.
  //
  // Kód je od fáze 2b vlastnost zařazení do KONKRÉTNÍHO zpěvníku, ne písně
  // (viz PolozkaZpevniku) — kolidovat proto může jen s kódy VE ZPĚVNÍCÍCH,
  // které tenhle import osloví. Tenhle předletový (klientský) warning je
  // ale jen pro KATEGORIE — server tam kolizi odmítá (celý import se
  // zastaví). Cílový zpěvník (`cely_zpevnik`, bod 4) kolizi naopak
  // automaticky přeřadí (viz import_pisni.proved_import), takže by ho tenhle
  // blokující warning jen zbytečně strašil — jeho případné přeřazení uvidí
  // až v souhrnu po dokončení importu (`prejmenovani_kodu`).
  const { data: vsechnyZpevniky } = useAllPages('/api/zpevniky/')
  const cilovaJmenaZpevniku = useMemo(() => {
    const jmena = new Set()
    for (const k of kategorie) if (k.vytvorit) jmena.add(k.nazev)
    return jmena
  }, [kategorie])
  const existingKody = useMemo(() => {
    const kody = new Set()
    for (const z of vsechnyZpevniky || []) {
      if (!cilovaJmenaZpevniku.has(z.nazev)) continue
      for (const p of z.pisne) kody.add(p.kod)
    }
    return kody
  }, [vsechnyZpevniky, cilovaJmenaZpevniku])

  const selectFile = useCallback(async (file) => {
    if (!file) return
    fileRef.current = file
    setFileName(file.name)
    // Preset (import z konkrétního zpěvníku) se nepřepisuje názvem souboru —
    // jen výchozí "nový zpěvník" better-guess bez presetu.
    setCelyZpevnik((prev) =>
      presetZpevnikId ? prev : { mod: 'novy', nazev: file.name.replace(/\.pdf$/i, ''), existujiciId: '' },
    )
    setParseError(null)
    setStep('parsing')
    setParseProgress({ done: 0, total: 0 })

    try {
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current)
      const url = URL.createObjectURL(file)
      objectUrlRef.current = url

      const pdfDoc = await pdfjsLib.getDocument(url).promise
      pdfDocRef.current = pdfDoc

      const parsedPages = await parseAllPages(pdfDoc, (done, total) =>
        setParseProgress({ done, total }),
      )
      setPages(parsedPages)

      const labels = await navrhniNazvyKategorii(pdfDoc)
      kategorieLabelsRef.current = labels
      // Kategorie se skutečně sestaví až na kroku Kategorie (goToKategorie),
      // kdy jsou k dispozici i kódy dopočítané z "Kódy od" — bez nich by
      // zpěvník bez vlastních kódů (viz 80s_zpevnik.pdf) skončil na tomhle
      // kroku s prázdným seznamem kategorií.
      setKategorie([])

      setStep('review')
    } catch (err) {
      setParseError(err?.message || 'PDF se nepodařilo zpracovat.')
      setStep('upload')
    }
  }, [presetZpevnikId])

  const updatePage = useCallback((pageNumber, patch) => {
    setPages((prev) => prev.map((p) => (p.page === pageNumber ? { ...p, ...patch } : p)))
  }, [])

  const { songs, orphanConstinuations } = useMemo(() => groupPagesIntoSongs(pages), [pages])

  const kodyOd = kodyOdText.trim() === '' ? null : Number(kodyOdText)
  const vychoziKodyOd = useMemo(() => dalsiVolnaStovka(existingKody), [existingKody])

  // Skutečná data, se kterými appka od teď pracuje — songs s DOPOČÍTANÝMI
  // kódy tam, kde chybí. Ruční/parsovaný kód má vždy přednost (viz
  // kodyAuto.js), takže tohle songs jen DOPLŇUJE, nikdy nepřepisuje.
  const resolvedSongs = useMemo(
    () => prirazKody(songs, kodyOd, existingKody),
    [songs, kodyOd, existingKody],
  )
  // Strana -> dopočítaný kód, pro zobrazení v tabulce u řádků, které ho
  // samy nemají (viz ImportReviewTable — kod input tam ukazuje návrh, ale
  // teprve zápisem se stane "ručním").
  const resolvedKodInfoByPage = useMemo(() => {
    const mapa = new Map()
    for (const s of resolvedSongs) mapa.set(s.definujiciStrana, { kod: s.kod, odhad: Boolean(s.kodOdhad) })
    return mapa
  }, [resolvedSongs])

  const problems = useMemo(
    () => analyzeProblems(pages, resolvedSongs, orphanConstinuations, existingKody),
    [pages, resolvedSongs, orphanConstinuations, existingKody],
  )
  const jeValidni = useMemo(
    () => planJeValidni(resolvedSongs, orphanConstinuations, problems),
    [resolvedSongs, orphanConstinuations, problems],
  )
  const pocetProblemu = useMemo(
    () => [...problems.values()].reduce((sum, list) => sum + list.length, 0),
    [problems],
  )

  const updateKategorie = useCallback((digit, patch) => {
    setKategorie((prev) => prev.map((k) => (k.digit === digit ? { ...k, ...patch } : k)))
  }, [])

  const updateCelyZpevnik = useCallback((patch) => {
    setCelyZpevnik((prev) => ({ ...prev, ...patch }))
  }, [])

  const celyZpevnikValidni =
    celyZpevnik.mod === 'existujici' ? Boolean(celyZpevnik.existujiciId) : Boolean(celyZpevnik.nazev.trim())

  const goToReview = useCallback(() => setStep('review'), [])
  // Kategorie se staví TADY, ne při parsování — teprve teď jsou k dispozici
  // kódy dopočítané z "Kódy od" (viz resolvedSongs výš). Návrat na Kódy od
  // a znovu sem proto kategorie přestaví od začátku (ztratí se ruční úpravy
  // názvů z minula) — u kroku, který se typicky projde jednou, to je únosná
  // cena za to, že se rovnou počítá se správnými kódy.
  const goToKategorie = useCallback(() => {
    setKategorie(buildKategorieState(resolvedSongs, kategorieLabelsRef.current))
    setStep('kategorie')
  }, [resolvedSongs])

  const submit = useCallback(async () => {
    if (!celyZpevnikValidni) return
    setSubmitError(null)
    setStep('submitting')
    try {
      const data = await submitImport(fileRef.current, resolvedSongs, kategorie, celyZpevnik)
      setResult({ ok: true, data })
      setStep('result')
    } catch (err) {
      setSubmitError(extractErrorMessage(err, CHYBA_IMPORTU))
      setStep('kategorie')
    }
  }, [resolvedSongs, kategorie, celyZpevnik, celyZpevnikValidni])

  const zacitZnovu = useCallback(() => {
    fileRef.current = null
    pdfDocRef.current = null
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current)
    objectUrlRef.current = null
    kategorieLabelsRef.current = new Map()
    setFileName('')
    setPages([])
    setKategorie([])
    setKodyOdText('')
    setCelyZpevnik(prazdnyCil(presetZpevnikId))
    setResult(null)
    setSubmitError(null)
    setParseError(null)
    setStep('upload')
  }, [presetZpevnikId])

  return {
    step,
    fileName,
    pages,
    updatePage,
    songs: resolvedSongs,
    resolvedKodInfoByPage,
    kodyOdText,
    setKodyOdText,
    vychoziKodyOd,
    orphanConstinuations,
    problems,
    pocetProblemu,
    jeValidni,
    kategorie,
    updateKategorie,
    celyZpevnik,
    updateCelyZpevnik,
    celyZpevnikValidni,
    vsechnyZpevniky: vsechnyZpevniky || [],
    parseProgress,
    parseError,
    submitError,
    result,
    pdfDoc: pdfDocRef.current,
    selectFile,
    goToReview,
    goToKategorie,
    submit,
    zacitZnovu,
  }
}
