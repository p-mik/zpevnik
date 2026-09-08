import { useEffect, useRef, useState } from 'react'
import { fetchBlob } from '../api/client'
import pdfjsLib from './pdfjs'

// Načte celé PDF najednou (soubory jsou stovky kB, viz README) a vrátí
// pdf.js dokument. Když se `path` změní (přepnutí verze) a nové načtení
// selže, PŘEDCHOZÍ dokument zůstává ve `pdfDoc` — rozečtené noty nesmí
// zmizet jen proto, že se nepovedlo přepnout na jinou verzi.
export function usePdfDocument(path) {
  const [pdfDoc, setPdfDoc] = useState(null)
  const [loading, setLoading] = useState(Boolean(path))
  const [error, setError] = useState(null)
  const objectUrlRef = useRef(null)
  const requestIdRef = useRef(0)

  useEffect(() => {
    if (!path) {
      setPdfDoc(null)
      setLoading(false)
      setError(null)
      return
    }

    const requestId = ++requestIdRef.current
    let cancelled = false
    setLoading(true)
    setError(null)

    ;(async () => {
      try {
        const blob = await fetchBlob(path)
        if (cancelled || requestId !== requestIdRef.current) return
        const url = URL.createObjectURL(blob)
        const doc = await pdfjsLib.getDocument(url).promise
        if (cancelled || requestId !== requestIdRef.current) {
          doc.destroy()
          URL.revokeObjectURL(url)
          return
        }
        if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current)
        objectUrlRef.current = url
        setPdfDoc(doc)
        setLoading(false)
      } catch (err) {
        if (cancelled || requestId !== requestIdRef.current) return
        setError(err)
        setLoading(false)
      }
    })()

    return () => {
      cancelled = true
    }
  }, [path])

  // Úklid starého dokumentu při náhradě novým i při odmountování — vždy
  // po tom, co se `pdfDoc` reálně změní (cleanup dostane PŘEDCHOZÍ hodnotu).
  useEffect(() => {
    return () => {
      pdfDoc?.destroy()
    }
  }, [pdfDoc])

  useEffect(() => {
    return () => {
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current)
    }
  }, [])

  return { pdfDoc, loading, error }
}
