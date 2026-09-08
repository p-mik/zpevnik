import { useEffect, useState } from 'react'

// Spočítá render-scale, kterým se stránka vejde do kontejneru — 'width'
// (běžná čtečka, svisle se scrolluje) nebo 'contain' (stage mode, celá
// stránka musí být vidět naráz, žádný scroll). Reaguje na resize/otočení
// tabletu přes ResizeObserver.
export function useFitScale(pdfDoc, containerRef, fitMode = 'width') {
  const [scale, setScale] = useState(null)

  useEffect(() => {
    if (!pdfDoc || !containerRef.current) {
      setScale(null)
      return
    }

    let cancelled = false
    let naturalWidth = null
    let naturalHeight = null

    async function recompute() {
      const el = containerRef.current
      if (!el) return
      if (naturalWidth == null) {
        const page = await pdfDoc.getPage(1)
        if (cancelled) return
        const viewport = page.getViewport({ scale: 1 })
        naturalWidth = viewport.width
        naturalHeight = viewport.height
      }
      // clientWidth/Height zahrnují i padding kontejneru — bez odečtení by
      // canvas vycházel systematicky moc velký a vyráběl si vlastní
      // scrollbar navíc (viditelné jako zbytečný vodorovný scroll).
      const style = window.getComputedStyle(el)
      const paddingX = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight)
      const paddingY = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom)
      const availableWidth = el.clientWidth - paddingX
      const availableHeight = el.clientHeight - paddingY
      if (!availableWidth) return
      const next =
        fitMode === 'contain'
          ? Math.min(availableWidth / naturalWidth, availableHeight / naturalHeight)
          : availableWidth / naturalWidth
      if (!cancelled && next > 0) setScale(next)
    }

    recompute()

    const observer = new ResizeObserver(() => recompute())
    observer.observe(containerRef.current)

    return () => {
      cancelled = true
      observer.disconnect()
    }
  }, [pdfDoc, containerRef, fitMode])

  return scale
}
