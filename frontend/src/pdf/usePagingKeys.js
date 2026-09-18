import { useEffect } from 'react'

const PREV_KEYS = new Set(['ArrowLeft', 'ArrowUp', 'PageUp'])
const NEXT_KEYS = new Set(['ArrowRight', 'ArrowDown', 'PageDown', ' '])
const TYPING_TAGS = new Set(['INPUT', 'TEXTAREA', 'SELECT'])

function isTypingTarget(target) {
  if (!(target instanceof Element)) return false
  return TYPING_TAGS.has(target.tagName) || target.isContentEditable
}

// Šipky/PageUp/PageDown/mezerník. Nejsou to jen desktop zkratky — Bluetooth
// footswitch pedály se systému hlásí jako klávesnice, takže tohle je zároveň
// příprava na pedál (viz zadání fáze 1d).
export function usePagingKeys({ onPrev, onNext, enabled = true }) {
  useEffect(() => {
    if (!enabled) return

    function onKeyDown(e) {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      // Když se píše (hledání v rychlém výběru písně), mezerník a šipky
      // patří poli, ne listování — jinak by nešlo napsat ani mezeru.
      if (isTypingTarget(e.target)) return
      if (PREV_KEYS.has(e.key)) {
        e.preventDefault()
        onPrev()
      } else if (NEXT_KEYS.has(e.key)) {
        e.preventDefault()
        onNext()
      }
    }

    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [onPrev, onNext, enabled])
}
