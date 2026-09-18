import { useEffect, useRef, useState } from 'react'
import './PagePreviewModal.css'

// Náhled jedné strany PDF ve čtecí velikosti, se šipkami na sousední strany
// CELÉHO dokumentu (ne jen strany rozpoznané písně) — u vícesloupcových a
// pokračovacích stran miniatura nestačí poznat, co je na stránce doopravdy,
// tohle je rychlejší než stahovat/otevírat PDF bokem.
export default function PagePreviewModal({ pdfDoc, pageNumber, numPages, onClose, onNavigate }) {
  const canvasRef = useRef(null)
  const wrapRef = useRef(null)
  const [nacita, setNacita] = useState(true)

  useEffect(() => {
    function naKlavesu(e) {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowLeft') onNavigate(-1)
      else if (e.key === 'ArrowRight') onNavigate(1)
    }
    window.addEventListener('keydown', naKlavesu)
    return () => window.removeEventListener('keydown', naKlavesu)
  }, [onClose, onNavigate])

  useEffect(() => {
    if (!pdfDoc || !pageNumber) return undefined
    let zruseno = false
    setNacita(true)
    ;(async () => {
      const page = await pdfDoc.getPage(pageNumber)
      const wrap = wrapRef.current
      if (!wrap) return
      // "Contain" fit na SKUTEČNĚ dostupný prostor (šířka i výška), stejná
      // logika jako useFitScale(..., 'contain') ve čtečce/stage módu. Dřív
      // se počítala jen šířka — na vyšší stránce, než kolik se vejde na
      // výšku, přetekl canvas ven a `align-items: center` v přetékajícím
      // kontejneru schoval horní i dolní okraj stejným dílem: nahoru (ta
      // nejdůležitější část, hlavička) bylo vidět, jen když se scrollovalo
      // NAHORU, což nikoho nenapadne zkusit jako první.
      const dostupnaSirka = wrap.clientWidth
      const dostupnaVyska = wrap.clientHeight
      const naturalViewport = page.getViewport({ scale: 1 })
      const scale = Math.min(
        dostupnaSirka / naturalViewport.width,
        dostupnaVyska / naturalViewport.height,
      )
      const viewport = page.getViewport({ scale })
      if (zruseno) return
      const canvas = canvasRef.current
      if (!canvas) return
      canvas.width = Math.ceil(viewport.width)
      canvas.height = Math.ceil(viewport.height)
      const ctx = canvas.getContext('2d')
      await page.render({ canvasContext: ctx, viewport }).promise
      if (!zruseno) setNacita(false)
    })()
    return () => {
      zruseno = true
    }
  }, [pdfDoc, pageNumber])

  return (
    <div className="page-preview-backdrop" onClick={onClose}>
      <div className="page-preview-panel" onClick={(e) => e.stopPropagation()}>
        <div className="page-preview-head">
          <span className="page-preview-title">
            Strana {pageNumber} / {numPages}
          </span>
          <button type="button" className="page-preview-close" onClick={onClose} aria-label="Zavřít náhled">
            ✕
          </button>
        </div>
        <div className="page-preview-body">
          <button
            type="button"
            className="page-preview-nav page-preview-prev"
            onClick={() => onNavigate(-1)}
            disabled={pageNumber <= 1}
            aria-label="Předchozí strana"
          >
            ‹
          </button>
          <div className="page-preview-canvas-wrap" ref={wrapRef}>
            {nacita && <span className="loading-pulse">Načítám…</span>}
            <canvas ref={canvasRef} className="page-preview-canvas" hidden={nacita} />
          </div>
          <button
            type="button"
            className="page-preview-nav page-preview-next"
            onClick={() => onNavigate(1)}
            disabled={pageNumber >= numPages}
            aria-label="Další strana"
          >
            ›
          </button>
        </div>
      </div>
    </div>
  )
}
