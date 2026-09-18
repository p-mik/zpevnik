import { Link, useNavigate } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { usePdfDocument } from './usePdfDocument'
import { usePageRenderCache } from './usePageRenderCache'
import { useFitScale } from './useFitScale'
import { usePinchZoom } from './usePinchZoom'
import { usePagingKeys } from './usePagingKeys'
import { requestDocumentFullscreen } from './fullscreen'
import PdfPageCanvas from './PdfPageCanvas'
import SongQuickPicker from './SongQuickPicker'
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
  zpevnikLabel,
  zpevnikId,
  versionSwitcher,
  uploadButton,
  stageHref,
  sessionBanner,
  prevSongHref,
  nextSongHref,
  pickerHrefFor,
  currentSongId,
  annotationToggle,
  annotationBar,
  renderOverlay,
}) {
  const navigate = useNavigate()
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

  // Na první/poslední straně "přeteče" do sousední písně, pokud je kam —
  // jedna dvojice tlačítek/kláves pro obojí, ať to nevypadá rozbité u
  // (převažujících) jednostránkových písní, kde by jinak Další/Předchozí
  // nikdy nedělalo nic.
  const goPrev = () => {
    if (page > 1) setPage((p) => p - 1)
    else if (prevSongHref) navigate(prevSongHref)
  }
  const goNext = () => {
    if (page < numPages) setPage((p) => p + 1)
    else if (nextSongHref) navigate(nextSongHref)
  }

  usePagingKeys({ onPrev: goPrev, onNext: goNext, enabled: Boolean(pdfDoc) && !unavailableMessage })

  if (unavailableMessage) {
    return (
      <div className="reader-page">
        <ReaderTopbar
          backHref={backHref}
          backLabel={backLabel}
          codeLabel={codeLabel}
          title={title}
          subtitle={subtitle}
          zpevnikLabel={zpevnikLabel}
        />
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
        zpevnikLabel={zpevnikLabel}
        versionSwitcher={versionSwitcher}
        uploadButton={uploadButton}
        annotationToggle={annotationToggle}
        stageHref={stageHref}
        pickerHrefFor={pickerHrefFor}
        currentSongId={currentSongId}
        zpevnikId={zpevnikId}
      />

      {annotationBar}

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
                overlay={renderOverlay?.(page)}
              />
            </div>
          </div>

          <footer className="reader-pagebar">
            <button
              type="button"
              className="btn reader-page-btn"
              onClick={goPrev}
              disabled={page <= 1 && !prevSongHref}
              aria-label={page > 1 ? 'Předchozí strana' : 'Předchozí píseň'}
            >
              ‹ {page > 1 ? 'Předchozí' : 'Předchozí píseň'}
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
              disabled={page >= numPages && !nextSongHref}
              aria-label={page < numPages ? 'Další strana' : 'Další píseň'}
            >
              {page < numPages ? 'Další' : 'Další píseň'} ›
            </button>
          </footer>
        </>
      )}
    </div>
  )
}

function ReaderTopbar({
  backHref,
  backLabel,
  codeLabel,
  title,
  subtitle,
  zpevnikLabel,
  versionSwitcher,
  uploadButton,
  annotationToggle,
  stageHref,
  pickerHrefFor,
  currentSongId,
  zpevnikId,
}) {
  const [pickerOpen, setPickerOpen] = useState(false)
  const titleRef = useRef(null)

  return (
    <header className="reader-topbar">
      <Link to={backHref} className="breadcrumb-back reader-back">
        ← {backLabel}
      </Link>
      <button
        ref={titleRef}
        type="button"
        className="reader-title"
        onClick={() => setPickerOpen((v) => !v)}
        aria-expanded={pickerOpen}
        aria-label="Přepnout na jinou píseň"
      >
        {codeLabel && <span className="code-chip reader-code">{codeLabel}</span>}
        <span className="reader-title-text">
          {title}
          {subtitle && <span className="reader-subtitle"> · {subtitle}</span>}
          {/* Ve kterém zpěvníku jsem — nenápadně, viz PC_zpevnik_kontext_zpevniku. */}
          {zpevnikLabel && <span className="reader-subtitle reader-zpevnik-label"> · {zpevnikLabel}</span>}
        </span>
        <span className="reader-title-caret" aria-hidden="true">
          {pickerOpen ? '▴' : '▾'}
        </span>
      </button>
      <div className="reader-topbar-actions">
        {annotationToggle}
        {uploadButton}
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
      {pickerOpen && zpevnikId && (
        <SongQuickPicker
          onClose={() => setPickerOpen(false)}
          anchorRef={titleRef}
          hrefFor={pickerHrefFor}
          currentSongId={currentSongId}
          zpevnikId={zpevnikId}
        />
      )}
    </header>
  )
}
