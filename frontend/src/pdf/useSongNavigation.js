import { useMemo } from 'react'
import { useApiResource } from '../hooks/useApiResource'
import { useAllPages } from '../hooks/useAllPages'

// Sousední píseň v pořadí podle kódu (stejná konvence jako všude jinde v
// appce — řazení je vždy podle kódu, ne podle názvu). Když je zadaný
// `zpevnikId`, hledá se sousedství JEN v rámci toho zpěvníku (typický
// scénář na zkoušce/koncertě — kapelník listuje konkrétním zpěvníkem, ne
// celou knihovnou); jinak se hledá v celém seznamu písní.
export function useSongNavigation(currentSongId, zpevnikId) {
  const zpevnikRes = useApiResource(zpevnikId ? `/api/zpevniky/${zpevnikId}/` : null)
  const allRes = useAllPages(zpevnikId ? null : '/api/pisne/?ordering=kod')

  const list = zpevnikId ? zpevnikRes.data?.pisne : allRes.data

  return useMemo(() => {
    if (!list) return { prevSong: null, nextSong: null }
    const sorted = [...list].sort((a, b) => a.kod - b.kod)
    const idx = sorted.findIndex((s) => String(s.id) === String(currentSongId))
    if (idx === -1) return { prevSong: null, nextSong: null }
    return {
      prevSong: idx > 0 ? sorted[idx - 1] : null,
      nextSong: idx < sorted.length - 1 ? sorted[idx + 1] : null,
    }
  }, [list, currentSongId])
}

// Sousední píseň ve VEŘEJNÉM zpěvníku — data má appka už stažená (celý
// seznam písní zpěvníku přijde v jedné odpovědi), žádný další dotaz netřeba.
export function useSongNavigationFromList(pisne, currentKod) {
  return useMemo(() => {
    if (!pisne) return { prevSong: null, nextSong: null }
    const sorted = [...pisne].sort((a, b) => a.kod - b.kod)
    const idx = sorted.findIndex((s) => String(s.kod) === String(currentKod))
    if (idx === -1) return { prevSong: null, nextSong: null }
    return {
      prevSong: idx > 0 ? sorted[idx - 1] : null,
      nextSong: idx < sorted.length - 1 ? sorted[idx + 1] : null,
    }
  }, [pisne, currentKod])
}
