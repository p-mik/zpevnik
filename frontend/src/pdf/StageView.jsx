import { Link, useNavigate } from 'react-router-dom'
import { useCallback, useEffect, useRef, useState } from 'react'
import { usePdfDocument } from './usePdfDocument'
import { usePageRenderCache } from './usePageRenderCache'
import { useFitScale } from './useFitScale'
import { usePagingKeys } from './usePagingKeys'
import { useWakeLock } from './useWakeLock'
import { exitDocumentFullscreen } from './fullscreen'
import PdfPageCanvas from './PdfPageCanvas'
import SongQuickPicker from './SongQuickPicker'
import StageInstallHint from './StageInstallHint'
import './StageView.css'

const OVERLAY_TIMEOUT_MS = 4000
// Tap, který zavřel rychlý výběr písně, se do tohohle času nebere jako tap
// na noty (otočení stránky / skrytí overlaye).
const TAP_SWALLOW_MS = 500

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
  prevSongHref,
  nextSongHref,
  pickerHrefFor,
  currentSongId,
}) {
  const navigate = useNavigate()
  const containerRef = useRef(null)
  const titleRef = useRef(null)
  const [page, setPage] = useState(1)
  const [overlayVisible, setOverlayVisible] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const hideTimerRef = useRef(null)
  const swallowTapsUntilRef = useRef(0)

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

  // Dvě věci v jednom:
  // 1. Hned po vstupu se ovládání (hlavně "jak se odsud dostanu ven") krátce
  //    mihne — jinak by se objevilo, jen když uživatel ví, že má ťuknout
  //    doprostřed, což je přesně to "nezjevné", co zadání zakazuje. Po pár
  //    vteřinách zase zmizí a při hraní nepřekáží.
  // 2. Rychlý výběr písně žije v overlayi — dokud je otevřený, overlay se
  //    nesmí sám schovat (zmizel by i s ním). Po zavření zase běží odpočet.
  useEffect(() => {
    if (pickerOpen) {
      clearTimeout(hideTimerRef.current)
      setOverlayVisible(true)
    } else {
      flashOverlay(true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickerOpen])

  const closePicker = useCallback((reason) => {
    setPickerOpen(false)
    // Pointerdown mimo panel zavře výběr, ale ten samý tap by pak jako click
    // dopadl na noty a otočil stránku. Krátce ho proto v handleTap ignorujeme.
    if (reason === 'outside') swallowTapsUntilRef.current = performance.now() + TAP_SWALLOW_MS
  }, [])

  // Při přechodu na jinou píseň tap zónou / klávesou se panel zavře sám
  // (výběr z panelu si zavření hlásí přes onClose('select')).
  useEffect(() => {
    setPickerOpen(false)
  }, [pdfPath])

  useEffect(() => {
    if (sessionLost) flashOverlay(true)
  }, [sessionLost, flashOverlay])

  // Na první/poslední straně "přeteče" do sousední písně, pokud je kam —
  // stejná logika jako v běžné čtečce, navíc platí i pro tap zóny a
  // klávesy/pedál (usePagingKeys volá tytéž funkce). `navigate` musí být
  // mimo updater funkci setPage — ta musí zůstat čistá, jinak by ji React
  // mohl zavolat vícekrát (StrictMode) a navigace by se spustila dvakrát.
  const goPrev = useCallback(() => {
    if (page > 1) setPage((p) => p - 1)
    else if (prevSongHref) navigate(prevSongHref)
  }, [page, prevSongHref, navigate])
  const goNext = useCallback(() => {
    if (page < numPages) setPage((p) => p + 1)
    else if (nextSongHref) navigate(nextSongHref)
  }, [page, numPages, nextSongHref, navigate])

  usePagingKeys({ onPrev: goPrev, onNext: goNext, enabled: Boolean(pdfDoc) && !unavailableMessage })

  function handleTap(e) {
    if (performance.now() < swallowTapsUntilRef.current) return
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
          <button
            ref={titleRef}
            type="button"
            className="stage-overlay-title"
            onClick={() => setPickerOpen((v) => !v)}
            aria-expanded={pickerOpen}
            aria-label="Přepnout na jinou píseň"
          >
            {codeLabel && <span className="stage-code">{codeLabel}</span>}
            <span className="stage-overlay-title-text">{title}</span>
            <span className="stage-overlay-caret" aria-hidden="true">
              {pickerOpen ? '▴' : '▾'}
            </span>
          </button>
          {pickerOpen && (
            <SongQuickPicker
              onClose={closePicker}
              anchorRef={titleRef}
              hrefFor={pickerHrefFor}
              currentSongId={currentSongId}
            />
          )}
        </div>

        <Link
          to={exitHref}
          className="stage-exit"
          aria-label="Ukončit stage mode"
          title="Ukončit stage mode"
          onClick={(e) => e.stopPropagation()}
        >
          ✕
        </Link>

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

      <StageInstallHint />
    </div>
  )
}
