import { useMemo } from 'react'
import { useApiResource } from '../hooks/useApiResource'
import { useAllPages } from '../hooks/useAllPages'

// Sousední píseň V RÁMCI ZPĚVNÍKU, řazeno podle JEHO vlastního kódu (viz
// PolozkaZpevniku — kód je vlastnost zařazení, ne písně). Návrhové pravidlo
// (viz PC_zpevnik_kontext_zpevniku): čtečka a stage mode jsou VŽDY
// podkategorií jednoho zpěvníku, takže `zpevnikId` sem chodí vždy vyřešené
// (viz useZpevnikKontext) — bez něj (píseň bez jediného zařazení,
// degenerovaný okrajový případ) navigace prostě není, žádný tichý návrat
// na "napříč vším" (na to je útěk useGlobalSongNavigation, viz níž — a ten
// používá jen SongDetailPage jako rozcestník mezi zpěvníky, ne čtečka).
export function useSongNavigation(currentSongId, zpevnikId) {
  const { data: zpevnik } = useApiResource(zpevnikId ? `/api/zpevniky/${zpevnikId}/` : null)
  const list = zpevnik?.pisne

  return useMemo(() => {
    if (!zpevnikId || !list) return { prevSong: null, nextSong: null }
    const sorted = [...list].sort((a, b) => a.kod - b.kod)
    const idx = sorted.findIndex((s) => String(s.id) === String(currentSongId))
    if (idx === -1) return { prevSong: null, nextSong: null }
    return {
      prevSong: idx > 0 ? sorted[idx - 1] : null,
      nextSong: idx < sorted.length - 1 ? sorted[idx + 1] : null,
    }
  }, [list, currentSongId, zpevnikId])
}

// Sousední píseň NAPŘÍČ VŠÍM podle názvu — jen pro SongDetailPage, který je
// schválně rozcestník mezi zpěvníky, ne čtečka/stage (viz komentář tam).
// Kód se tu neukazuje: je vlastnost zařazení do konkrétního zpěvníku, napříč
// vším nejde jednoznačně vybrat, které.
export function useGlobalSongNavigation(currentSongId) {
  const { data: list } = useAllPages('/api/pisne/?ordering=nazev')

  return useMemo(() => {
    if (!list) return { prevSong: null, nextSong: null }
    const sorted = [...list].sort((a, b) => a.nazev.localeCompare(b.nazev, 'cs'))
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
