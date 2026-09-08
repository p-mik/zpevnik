import { Link } from 'react-router-dom'
import { useCallback, useEffect, useRef, useState } from 'react'
import { usePdfDocument } from './usePdfDocument'
import { usePageRenderCache } from './usePageRenderCache'
import { useFitScale } from './useFitScale'
import { usePagingKeys } from './usePagingKeys'
import { useWakeLock } from './useWakeLock'
import { exitDocumentFullscreen } from './fullscreen'
import PdfPageCanvas from './PdfPageCanvas'
import './StageView.css'

const OVERLAY_TIMEOUT_MS = 4000

// Fullscreen čtení bez appkového UI — vlastní tokeny (--stage-*), žádný
// --app-* odstín. `position: fixed` kryje celou obrazovku bez ohledu na to,
// jestli se povedlo získat i skutečný Fullscreen API (viz fullscreen.js).
export default function StageView({
  pdfPath,
  unavailableTitle,
  unavailableMessage,
  title,
  codeLabel,
  exitHref,
  sessionLost,
}) {
  const containerRef = useRef(null)
  const [page, setPage] = useState(1)
  const [overlayVisible, setOverlayVisible] = useState(false)
  const hideTimerRef = useRef(null)

  const { pdfDoc, loading, error } = usePdfDocument(unavailableMessage ? null : pdfPath)
  const scale = useFitScale(pdfDoc, containerRef, 'contain')
  const { getPageCanvas, peek, prefetch } = usePageRenderCache(pdfDoc, scale)
  const numPages = pdfDoc?.numPages ?? 0

  useWakeLock(Boolean(pdfDoc))

  useEffect(() => {
    setPage(1)
  }, [pdfPath])

  useEffect(() => {
    if (!pdfDoc) return
    prefetch(page + 1)
    prefetch(page - 1)
  }, [pdfDoc, page, prefetch])

  useEffect(() => exitDocumentFullscreen, [])

  useEffect(() => () => clearTimeout(hideTimerRef.current), [])

  const flashOverlay = useCallback((visible) => {
    setOverlayVisible(visible)
    clearTimeout(hideTimerRef.current)
    if (visible) {
      hideTimerRef.current = setTimeout(() => setOverlayVisible(false), OVERLAY_TIMEOUT_MS)
    }
  }, [])

  useEffect(() => {
    if (sessionLost) flashOverlay(true)
  }, [sessionLost, flashOverlay])

  const goPrev = useCallback(() => setPage((p) => Math.max(1, p - 1)), [])
  const goNext = useCallback(() => setPage((p) => Math.min(numPages, p + 1)), [numPages])

  usePagingKeys({ onPrev: goPrev, onNext: goNext, enabled: Boolean(pdfDoc) && !unavailableMessage })

  function handleTap(e) {
    const rect = e.currentTarget.getBoundingClientRect()
    const ratio = (e.clientX - rect.left) / rect.width
    if (ratio < 0.35) goPrev()
    else if (ratio > 0.65) goNext()
    else flashOverlay(!overlayVisible)
  }

  if (unavailableMessage) {
    return (
      <div className="stage-root stage-root-static">
        <div className="stage-unavailable">
          <h2>{unavailableTitle}</h2>
          <p>{unavailableMessage}</p>
          <Link to={exitHref} className="stage-btn">
            Zpět
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="stage-root">
      <div className="stage-tapzone" onClick={handleTap} ref={containerRef}>
        {loading && !pdfDoc && <span className="stage-loading">Načítám noty…</span>}
        {error && !pdfDoc && (
          <div className="stage-error">
            <p>{error.detail || 'PDF se nepodařilo načíst.'}</p>
          </div>
        )}
        {pdfDoc && (
          <PdfPageCanvas
            key={page}
            getPageCanvas={getPageCanvas}
            peek={peek}
            pageNumber={page}
            ariaLabel={`Strana ${page} z ${numPages}`}
            placeholderClassName="stage-loading pdf-page-placeholder"
          />
        )}
      </div>

      <div className={`stage-overlay${overlayVisible ? ' stage-overlay-visible' : ''}`}>
        <div className="stage-overlay-top">
          <span className="stage-overlay-title">
            {codeLabel && <span className="stage-code">{codeLabel}</span>}
            {title}
          </span>
          <Link to={exitHref} className="stage-exit" onClick={(e) => e.stopPropagation()}>
            Ukončit stage mode ✕
          </Link>
        </div>

        {sessionLost && (
          <p className="stage-session-banner">
            Přihlášení vypršelo — noty zůstávají, pro přepnutí verze se přihlas znovu.
          </p>
        )}

        {pdfDoc && numPages > 0 && (
          <div className="stage-overlay-bottom">
            <span className="stage-page-count">
              {page} / {numPages}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
