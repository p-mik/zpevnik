import { useCallback, useRef } from 'react'

// Renderuje stránku do vlastního (offscreen) canvasu. Kreslí se ve
// `devicePixelRatio`, aby to bylo ostré na retina tabletech — CSS velikost
// canvasu je `viewport` v CSS px, skutečné pixely jsou vynásobené DPR.
async function renderPageToCanvas(pdfDoc, pageNumber, scale) {
  const page = await pdfDoc.getPage(pageNumber)
  const viewport = page.getViewport({ scale })
  const outputScale = window.devicePixelRatio || 1

  const canvas = document.createElement('canvas')
  canvas.width = Math.ceil(viewport.width * outputScale)
  canvas.height = Math.ceil(viewport.height * outputScale)
  const ctx = canvas.getContext('2d')

  const renderTask = page.render({
    canvasContext: ctx,
    viewport,
    transform: outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : undefined,
  })
  await renderTask.promise

  return { canvas, cssWidth: viewport.width, cssHeight: viewport.height }
}

// Cache vykreslených stránek pro daný dokument+scale — přepnutí na sousední
// stránku je pak okamžité (viz `prefetch`), místo aby se čekalo na render.
export function usePageRenderCache(pdfDoc, scale) {
  const cacheRef = useRef(new Map())
  const inFlightRef = useRef(new Map())
  const keyRef = useRef({ pdfDoc: null, scale: null })

  // Reset musí proběhnout BĚHEM renderu, ne v useEffectu — efekty dětí
  // (PdfPageCanvas) běží dřív než efekt rodiče, takže by dítě stihlo
  // přečíst starou keš (jinou verzi) ještě předtím, než by se stihla
  // vyčistit, a na okamžik by ukázalo obsah špatné verze.
  if (keyRef.current.pdfDoc !== pdfDoc || keyRef.current.scale !== scale) {
    keyRef.current = { pdfDoc, scale }
    cacheRef.current = new Map()
    inFlightRef.current = new Map()
  }

  const peek = useCallback((pageNumber) => cacheRef.current.get(pageNumber), [])

  const getPageCanvas = useCallback(
    (pageNumber) => {
      if (!pdfDoc || !scale) return Promise.resolve(null)
      const cached = cacheRef.current.get(pageNumber)
      if (cached) return Promise.resolve(cached)

      let inflight = inFlightRef.current.get(pageNumber)
      if (!inflight) {
        inflight = renderPageToCanvas(pdfDoc, pageNumber, scale).then((result) => {
          cacheRef.current.set(pageNumber, result)
          inFlightRef.current.delete(pageNumber)
          return result
        })
        inFlightRef.current.set(pageNumber, inflight)
      }
      return inflight
    },
    [pdfDoc, scale],
  )

  const prefetch = useCallback(
    (pageNumber) => {
      if (!pdfDoc || pageNumber < 1 || pageNumber > pdfDoc.numPages) return
      getPageCanvas(pageNumber).catch(() => {})
    },
    [pdfDoc, getPageCanvas],
  )

  return { getPageCanvas, peek, prefetch }
}
