import { useMemo } from 'react'
import { useApiResource } from '../hooks/useApiResource'
import { useAllPages } from '../hooks/useAllPages'

// Sousední píseň v pořadí. Když je zadaný `zpevnikId`, hledá se sousedství
// JEN v rámci toho zpěvníku (typický scénář na zkoušce/koncertě — kapelník
// listuje konkrétním zpěvníkem, ne celou knihovnou), řazeno podle JEHO
// vlastního kódu (viz PolozkaZpevniku — kód je vlastnost tohohle zařazení).
// Bez zpevnikId (procházení napříč vším) kód není k dispozici vůbec — kód
// je od fáze 2b vlastnost zařazení do zpěvníku, ne písně — takže se řadí
// podle názvu, stejně jako plochý seznam píseň všude jinde v appce.
export function useSongNavigation(currentSongId, zpevnikId) {
  const zpevnikRes = useApiResource(zpevnikId ? `/api/zpevniky/${zpevnikId}/` : null)
  const allRes = useAllPages(zpevnikId ? null : '/api/pisne/?ordering=nazev')

  const list = zpevnikId ? zpevnikRes.data?.pisne : allRes.data
  const razeniPodleKodu = Boolean(zpevnikId)

  return useMemo(() => {
    if (!list) return { prevSong: null, nextSong: null }
    const sorted = razeniPodleKodu
      ? [...list].sort((a, b) => a.kod - b.kod)
      : [...list].sort((a, b) => a.nazev.localeCompare(b.nazev, 'cs'))
    const idx = sorted.findIndex((s) => String(s.id) === String(currentSongId))
    if (idx === -1) return { prevSong: null, nextSong: null }
    return {
      prevSong: idx > 0 ? sorted[idx - 1] : null,
      nextSong: idx < sorted.length - 1 ? sorted[idx + 1] : null,
    }
  }, [list, currentSongId, razeniPodleKodu])
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
