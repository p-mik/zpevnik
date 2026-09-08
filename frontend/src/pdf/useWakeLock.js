import { useEffect } from 'react'

// Nedovolí displeji zhasnout, dokud je aktivní stage mode. Wake Lock se
// prohlížečem samovolně uvolní, když stránka zmizí z popředí (přepnutí
// appky, zamčení) — po návratu se proto znovu vyžádá.
export function useWakeLock(active) {
  useEffect(() => {
    if (!active || !('wakeLock' in navigator)) return

    let released = false
    let sentinel = null

    async function acquire() {
      try {
        sentinel = await navigator.wakeLock.request('screen')
      } catch {
        // Nepodporováno, nebo dokument zrovna není viditelný — potichu se
        // nechá appka fungovat i bez toho, displej si prostě sám zhasne.
      }
    }

    acquire()

    function onVisibilityChange() {
      if (!released && document.visibilityState === 'visible') acquire()
    }
    document.addEventListener('visibilitychange', onVisibilityChange)

    return () => {
      released = true
      document.removeEventListener('visibilitychange', onVisibilityChange)
      sentinel?.release().catch(() => {})
    }
  }, [active])
}
