import { useEffect, useRef, useState } from 'react'
import './PdfPageCanvas.css'

// Vloží vykreslený canvas dané stránky do DOM. Když je stránka už v cache
// (viz `usePageRenderCache`), zobrazí se rovnou bez bliknutí placeholderu.
export default function PdfPageCanvas({
  getPageCanvas,
  peek,
  pageNumber,
  ariaLabel,
  placeholderClassName,
  zoom = 1,
  overlay,
}) {
  const containerRef = useRef(null)
  const [result, setResult] = useState(() => peek?.(pageNumber) ?? null)

  useEffect(() => {
    let cancelled = false
    const cached = peek?.(pageNumber)
    if (cached) {
      setResult(cached)
    } else {
      setResult(null)
      getPageCanvas(pageNumber)
        .then((res) => {
          if (!cancelled) setResult(res)
        })
        .catch(() => {})
    }
    return () => {
      cancelled = true
    }
  }, [getPageCanvas, peek, pageNumber])

  useEffect(() => {
    const container = containerRef.current
    if (!container || !result) return
    if (container.firstChild !== result.canvas) {
      container.innerHTML = ''
      result.canvas.setAttribute('role', 'img')
      if (ariaLabel) result.canvas.setAttribute('aria-label', ariaLabel)
      container.appendChild(result.canvas)
    }
    // Reálná CSS velikost (ne transform) — díky tomu při přiblížení funguje
    // posun přes běžný scroll kontejneru, ne přes vlastní JS.
    result.canvas.style.width = `${result.cssWidth * zoom}px`
    result.canvas.style.height = `${result.cssHeight * zoom}px`
  }, [result, ariaLabel, zoom])

  // Overlay (anotace) musí ležet přesně na stránce, ne na `.pdf-page-wrap` —
  // ten stránku jen centruje a bývá větší (min-width/min-height). Proto tenhle
  // mezikrok: box s přesným rozměrem vykreslené stránky, do kterého se vejde
  // canvas i vrstva nad ním. `--anotace-sirka` z něj dědí velikosti písma,
  // takže poznámky rostou se zoomem spolu s notami.
  const sirka = result ? result.cssWidth * zoom : null
  const vyska = result ? result.cssHeight * zoom : null

  return (
    <div className="pdf-page-wrap">
      {!result && (
        <span className={placeholderClassName || 'loading-pulse pdf-page-placeholder'}>
          Načítám stránku…
        </span>
      )}
      <div
        className="pdf-page-stack"
        style={
          result
            ? { width: `${sirka}px`, height: `${vyska}px`, '--anotace-sirka': `${sirka}px` }
            : undefined
        }
      >
        <div ref={containerRef} className="pdf-page-canvas" />
        {result && overlay}
      </div>
    </div>
  )
}
