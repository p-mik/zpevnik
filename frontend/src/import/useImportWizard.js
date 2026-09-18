import { useCallback, useMemo, useRef, useState } from 'react'
import pdfjsLib from '../pdf/pdfjs'
import { useAllPages } from '../hooks/useAllPages'
import { parseAllPages } from './parsePdfPages'
import { groupPagesIntoSongs, analyzeProblems, planJeValidni } from './planAnalysis'
import { navrhniNazvyKategorii, buildKategorieState } from './deriveKategorie'
import { submitImport } from './submitImport'
import { ApiError } from '../api/client'

function zplostiChybu(hodnota) {
  if (typeof hodnota === 'string') return [hodnota]
  if (Array.isArray(hodnota)) return hodnota.flatMap(zplostiChybu)
  if (hodnota && typeof hodnota === 'object') return Object.values(hodnota).flatMap(zplostiChybu)
  return [String(hodnota)]
}

function extractErrorMessage(err) {
  if (!(err instanceof ApiError)) return 'Import se nepodařilo provést.'
  if (err.detail) return err.detail
  if (err.fieldErrors) return zplostiChybu(err.fieldErrors).join(' ')
  return 'Import se nepodařilo provést.'
}

// STEP: 'upload' -> 'parsing' -> 'review' -> 'kategorie' -> 'submitting' -> 'result'
export function useImportWizard() {
  const [step, setStep] = useState('upload')
  const [fileName, setFileName] = useState('')
  const [pages, setPages] = useState([])
  const [kategorie, setKategorie] = useState([])
  // "Kniha jako celek" — nezávisle na kategoriích níž (viz zadání/diskuze:
  // kategorie jsou pro procházení, ale zpěvník coby celek musí jít jedním
  // odkazem/setlistem). Jméno se předvyplní z názvu souboru.
  const [celyZpevnik, setCelyZpevnik] = useState({ nazev: '', vytvorit: true })
  const [parseProgress, setParseProgress] = useState({ done: 0, total: 0 })
  const [parseError, setParseError] = useState(null)
  const [submitError, setSubmitError] = useState(null)
  const [result, setResult] = useState(null)

  const fileRef = useRef(null)
  const pdfDocRef = useRef(null)
  const objectUrlRef = useRef(null)

  // Existující kódy v DB — pro warning v tabulce ("duplicitní-kod-db").
  // Autoritativní kontrolu stejně dělá až server při potvrzení importu.
  const { data: existujiciPisne } = useAllPages('/api/pisne/')
  const existingKody = useMemo(
    () => new Set((existujiciPisne || []).map((p) => p.kod)),
    [existujiciPisne],
  )

  const selectFile = useCallback(async (file) => {
    if (!file) return
    fileRef.current = file
    setFileName(file.name)
    setCelyZpevnik({ nazev: file.name.replace(/\.pdf$/i, ''), vytvorit: true })
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

      const { songs } = groupPagesIntoSongs(parsedPages)
      const labels = await navrhniNazvyKategorii(pdfDoc)
      setKategorie(buildKategorieState(songs, labels))

      setStep('review')
    } catch (err) {
      setParseError(err?.message || 'PDF se nepodařilo zpracovat.')
      setStep('upload')
    }
  }, [])

  const updatePage = useCallback((pageNumber, patch) => {
    setPages((prev) => prev.map((p) => (p.page === pageNumber ? { ...p, ...patch } : p)))
  }, [])

  const { songs, orphanConstinuations } = useMemo(() => groupPagesIntoSongs(pages), [pages])
  const problems = useMemo(
    () => analyzeProblems(pages, songs, orphanConstinuations, existingKody),
    [pages, songs, orphanConstinuations, existingKody],
  )
  const jeValidni = useMemo(
    () => planJeValidni(songs, orphanConstinuations, problems),
    [songs, orphanConstinuations, problems],
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

  const goToReview = useCallback(() => setStep('review'), [])
  const goToKategorie = useCallback(() => setStep('kategorie'), [])

  const submit = useCallback(async () => {
    setSubmitError(null)
    setStep('submitting')
    try {
      const data = await submitImport(fileRef.current, songs, kategorie, celyZpevnik)
      setResult({ ok: true, data })
      setStep('result')
    } catch (err) {
      setSubmitError(extractErrorMessage(err))
      setStep('kategorie')
    }
  }, [songs, kategorie, celyZpevnik])

  const zacitZnovu = useCallback(() => {
    fileRef.current = null
    pdfDocRef.current = null
    if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current)
    objectUrlRef.current = null
    setFileName('')
    setPages([])
    setKategorie([])
    setCelyZpevnik({ nazev: '', vytvorit: true })
    setResult(null)
    setSubmitError(null)
    setParseError(null)
    setStep('upload')
  }, [])

  return {
    step,
    fileName,
    pages,
    updatePage,
    songs,
    orphanConstinuations,
    problems,
    pocetProblemu,
    jeValidni,
    kategorie,
    updateKategorie,
    celyZpevnik,
    updateCelyZpevnik,
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
