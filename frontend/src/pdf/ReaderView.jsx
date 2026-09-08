import { Link } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { usePdfDocument } from './usePdfDocument'
import { usePageRenderCache } from './usePageRenderCache'
import { useFitScale } from './useFitScale'
import { usePinchZoom } from './usePinchZoom'
import { usePagingKeys } from './usePagingKeys'
import { requestDocumentFullscreen } from './fullscreen'
import PdfPageCanvas from './PdfPageCanvas'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import EmptyState from '../components/EmptyState'
import '../components/ui.css'
import './ReaderView.css'

export default function ReaderView({
  pdfPath,
  unavailableTitle,
  unavailableMessage,
  backHref,
  backLabel = 'Zpět',
  codeLabel,
  title,
  subtitle,
  versionSwitcher,
  stageHref,
  sessionBanner,
}) {
  const containerRef = useRef(null)
  const [page, setPage] = useState(1)

  const { pdfDoc, loading, error } = usePdfDocument(unavailableMessage ? null : pdfPath)
  const scale = useFitScale(pdfDoc, containerRef, 'width')
  const { getPageCanvas, peek, prefetch } = usePageRenderCache(pdfDoc, scale)
  const { scale: zoom, handlers: zoomHandlers, reset: resetZoom, isZoomed } = usePinchZoom()

  const numPages = pdfDoc?.numPages ?? 0

  // Nová píseň/verze -> zpátky na první stránku.
  useEffect(() => {
    setPage(1)
  }, [pdfPath])

  // Každá nová stránka začíná na 100 % — přiblížení z předešlé by na jiné
  // stránce neznamenalo nic rozumného (viz jednostránkový canvas níž).
  useEffect(() => {
    resetZoom()
  }, [page, resetZoom])

  useEffect(() => {
    if (!pdfDoc) return
    prefetch(page + 1)
    prefetch(page - 1)
  }, [pdfDoc, page, prefetch])

  const goPrev = () => setPage((p) => Math.max(1, p - 1))
  const goNext = () => setPage((p) => Math.min(numPages, p + 1))

  usePagingKeys({ onPrev: goPrev, onNext: goNext, enabled: Boolean(pdfDoc) && !unavailableMessage })

  if (unavailableMessage) {
    return (
      <div className="reader-page">
        <ReaderTopbar backHref={backHref} backLabel={backLabel} codeLabel={codeLabel} title={title} subtitle={subtitle} />
        <EmptyState title={unavailableTitle || 'Bez not'} description={unavailableMessage} actionLabel="Zpět" actionHref={backHref} />
      </div>
    )
  }

  return (
    <div className="reader-page">
      <ReaderTopbar
        backHref={backHref}
        backLabel={backLabel}
        codeLabel={codeLabel}
        title={title}
        subtitle={subtitle}
        versionSwitcher={versionSwitcher}
        stageHref={stageHref}
      />

      {sessionBanner && (
        <div className="toast-error reader-banner" role="status">
          Přihlášení vypršelo. Rozečtené noty zůstávají, ale pro přepnutí verze se přihlas znovu.
        </div>
      )}
      {error && pdfDoc && (
        <div className="toast-error reader-banner" role="alert">
          {error.detail || 'Novou verzi se nepodařilo načíst, zůstáváš u předchozí.'}
        </div>
      )}

      {loading && !pdfDoc && <LoadingState label="Načítám noty…" />}
      {error && !pdfDoc && (
        <ErrorState
          message={error.detail || 'PDF se nepodařilo načíst.'}
        />
      )}

      {pdfDoc && (
        <>
          <div
            className="reader-viewport"
            ref={containerRef}
            {...zoomHandlers}
          >
            <div className="reader-page-center">
              <PdfPageCanvas
                key={page}
                getPageCanvas={getPageCanvas}
                peek={peek}
                pageNumber={page}
                zoom={zoom}
                ariaLabel={`Strana ${page} z ${numPages}`}
              />
            </div>
          </div>

          <footer className="reader-pagebar">
            <button
              type="button"
              className="btn reader-page-btn"
              onClick={goPrev}
              disabled={page <= 1}
              aria-label="Předchozí strana"
            >
              ‹ Předchozí
            </button>
            <span className="reader-page-count">
              {page} / {numPages}
              {isZoomed && (
                <button type="button" className="reader-zoom-reset" onClick={resetZoom}>
                  100 %
                </button>
              )}
            </span>
            <button
              type="button"
              className="btn reader-page-btn"
              onClick={goNext}
              disabled={page >= numPages}
              aria-label="Další strana"
            >
              Další ›
            </button>
          </footer>
        </>
      )}
    </div>
  )
}

function ReaderTopbar({ backHref, backLabel, codeLabel, title, subtitle, versionSwitcher, stageHref }) {
  return (
    <header className="reader-topbar">
      <Link to={backHref} className="breadcrumb-back reader-back">
        ← {backLabel}
      </Link>
      <div className="reader-title">
        {codeLabel && <span className="code-chip reader-code">{codeLabel}</span>}
        <span className="reader-title-text">
          {title}
          {subtitle && <span className="reader-subtitle"> · {subtitle}</span>}
        </span>
      </div>
      <div className="reader-topbar-actions">
        {versionSwitcher}
        {stageHref && (
          <Link
            to={stageHref}
            className="btn btn-secondary reader-stage-link"
            onClick={requestDocumentFullscreen}
          >
            Stage mode
          </Link>
        )}
      </div>
    </header>
  )
}
