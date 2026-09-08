import { useCallback, useMemo, useRef, useState } from 'react'

const MIN_SCALE = 1
const MAX_SCALE = 3

// Jen pinch (dva prsty) mění zoom. Posun při přiblížení řeší nativní scroll
// prohlížeče (kontejner má overflow: auto a canvas se zvětšuje reálnou CSS
// velikostí, ne transformem) — díky tomu funguje i setrvačné táhnutí na
// iPadu zadarmo a jedno prstem se nedá nic rozhodit, takže to nekoliduje
// s listováním přes Prev/Next.
export function usePinchZoom() {
  const [scale, setScale] = useState(1)
  const scaleRef = useRef(1)
  scaleRef.current = scale
  const pointers = useRef(new Map())
  const gesture = useRef(null)

  const reset = useCallback(() => setScale(1), [])

  const onPointerDown = useCallback((e) => {
    if (e.pointerType !== 'touch') return
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    e.currentTarget.setPointerCapture?.(e.pointerId)

    if (pointers.current.size === 2) {
      const pts = [...pointers.current.values()]
      gesture.current = {
        startDist: Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) || 1,
        startScale: scaleRef.current,
      }
    }
  }, [])

  const onPointerMove = useCallback((e) => {
    if (!pointers.current.has(e.pointerId)) return
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY })
    const g = gesture.current
    if (!g || pointers.current.size !== 2) return

    const pts = [...pointers.current.values()]
    const dist = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) || 1
    const next = (g.startScale * dist) / g.startDist
    setScale(Math.min(MAX_SCALE, Math.max(MIN_SCALE, next)))
  }, [])

  const endPointer = useCallback((e) => {
    pointers.current.delete(e.pointerId)
    gesture.current = null
  }, [])

  const handlers = useMemo(
    () => ({
      onPointerDown,
      onPointerMove,
      onPointerUp: endPointer,
      onPointerCancel: endPointer,
    }),
    [onPointerDown, onPointerMove, endPointer],
  )

  return { scale, handlers, reset, isZoomed: scale > 1.001 }
}
