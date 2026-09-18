import { useEffect, useRef, useState } from 'react'
import './PageThumbnail.css'

const THUMB_WIDTH = 90

// Malý, nezávislý na čtečkové keši (frontend/src/pdf/*) — tam se řeší jedna
// velká stránka najednou, tady desítky miniatur současně. Renderuje se líně,
// jen když je řádek v tabulce reálně vidět (IntersectionObserver), ať se
// při 89 stránkách nezasekne úvodní vykreslení.
export default function PageThumbnail({ pdfDoc, pageNumber }) {
  const containerRef = useRef(null)
  const [visible, setVisible] = useState(false)
  const [imgUrl, setImgUrl] = useState(null)

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setVisible(true)
          observer.disconnect()
        }
      },
      { rootMargin: '200px' },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (!visible || !pdfDoc) return
    let cancelled = false
    let url = null

    ;(async () => {
      const page = await pdfDoc.getPage(pageNumber)
      const naturalViewport = page.getViewport({ scale: 1 })
      const scale = THUMB_WIDTH / naturalViewport.width
      const viewport = page.getViewport({ scale })
      const canvas = document.createElement('canvas')
      canvas.width = Math.ceil(viewport.width)
      canvas.height = Math.ceil(viewport.height)
      const ctx = canvas.getContext('2d')
      await page.render({ canvasContext: ctx, viewport }).promise
      if (cancelled) return
      url = canvas.toDataURL('image/png')
      setImgUrl(url)
    })()

    return () => {
      cancelled = true
    }
  }, [visible, pdfDoc, pageNumber])

  return (
    <div ref={containerRef} className="page-thumb">
      {imgUrl ? (
        <img src={imgUrl} alt={`Náhled strany ${pageNumber}`} />
      ) : (
        <span className="page-thumb-placeholder" aria-hidden="true" />
      )}
    </div>
  )
}
