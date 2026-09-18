import { useLayoutEffect, useEffect, useMemo, useRef, useState } from 'react'
import SearchBar, { parseSearchQuery } from '../components/SearchBar'
import SongRow, { SongList } from '../components/SongRow'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import EmptyState from '../components/EmptyState'
import { useApiResource } from '../hooks/useApiResource'
import './SongQuickPicker.css'

// Rozbalovací rychlý výběr písně — hledání podle kódu/názvu, v malém panelu
// u titulku čtečky. Výběr je normální odkaz (SongRow). Panel se po něm
// zavře výslovně (onClose('select')) — spolehnout se jen na to, že navigace
// panel "zboří", nejde: výběr právě otevřené písně URL nezmění a panel by
// zůstal viset.
// `anchorRef` = tlačítko, které panel otevírá. Pointerdown na něm se NESMÍ
// brát jako "klik mimo" — jinak by druhý klik na titulek panel nejdřív zavřel
// (pointerdown) a hned zas otevřel (click toggle), takže by nešel zavřít.
// `hrefFor(song)` = kam vede výběr (výchozí je čtečka, stage mode chce stage).
// `onClose(reason)` dostane 'outside' | 'escape' — stage mode podle toho
// pozná, že tap mimo panel má panel jen zavřít, a ne zároveň otočit stránku.
// `currentSongId` = právě otevřená píseň: po otevření se seznam nascrolluje
// na ni a zvýrazní ji, ať se nezačíná vždy od začátku.
//
// `zpevnikId` — hledání je VŽDY v rámci jednoho zpěvníku (viz
// PC_zpevnik_kontext_zpevniku: čtečka i stage mode mají kontext vždy
// vyřešený, viz useZpevnikKontext). Číselný dotaz = přesná shoda kódu V TOM
// zpěvníku (na pódiu se píše "312" a hledá se hned, žádné dotazy na server).
// Zpěvník má typicky nízké desítky až stovky písní, takže se stáhne celý
// najednou (stejně jako SongbookPage) a filtruje/řadí se na klientu —
// rychlejší a jednodušší než stránkovaný dotaz na `/api/pisne/`, který navíc
// od fáze 2b kód vůbec nezná (je to vlastnost zařazení, ne písně).
export default function SongQuickPicker({ onClose, anchorRef, hrefFor, currentSongId, zpevnikId }) {
  const [query, setQuery] = useState('')
  const { data: zpevnik, loading, error } = useApiResource(`/api/zpevniky/${zpevnikId}/`)

  const panelRef = useRef(null)
  const listWrapRef = useRef(null)
  const scrolledToCurrentRef = useRef(false)
  const isSearching = query.trim() !== ''

  const items = useMemo(() => {
    const vse = zpevnik?.pisne || []
    const sorted = [...vse].sort((a, b) => a.kod - b.kod)
    const { kod, search } = parseSearchQuery(query)
    if (kod != null) return sorted.filter((s) => String(s.kod) === kod)
    if (search) {
      const q = search.toLocaleLowerCase('cs')
      return sorted.filter(
        (s) => s.nazev.toLocaleLowerCase('cs').includes(q) || s.interpret?.toLocaleLowerCase('cs').includes(q),
      )
    }
    return sorted
  }, [zpevnik, query])

  // Po otevření (bez hledání) se seznam nascrolluje k právě otevřené písni,
  // ať se nezačíná vždy od prvního kódu.
  useEffect(() => {
    if (scrolledToCurrentRef.current || currentSongId == null || isSearching || loading) return
    scrolledToCurrentRef.current = true
    const wrap = listWrapRef.current
    const row = wrap?.querySelector('.song-row-current')
    if (!wrap || !row) return
    const wrapRect = wrap.getBoundingClientRect()
    const rowRect = row.getBoundingClientRect()
    wrap.scrollTop += rowRect.top - wrapRect.top - (wrap.clientHeight - rowRect.height) / 2
  }, [items, loading, currentSongId, isSearching])

  // Panel sahá až dolů k okraji obrazovky. Kde začíná, závisí na výšce
  // lišty nad ním (čtečka vs. stage, zalomení na úzkém displeji) — změří se
  // a předá CSS jako proměnná, samotný výpočet výšky zůstává v CSS.
  useLayoutEffect(() => {
    function fit() {
      const el = panelRef.current
      if (!el) return
      el.style.setProperty('--song-picker-top', `${Math.round(el.getBoundingClientRect().top)}px`)
    }
    fit()
    window.addEventListener('resize', fit)
    return () => window.removeEventListener('resize', fit)
  }, [])

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') onClose('escape')
    }
    function onPointerDown(e) {
      const insidePanel = panelRef.current?.contains(e.target)
      const onAnchor = anchorRef?.current?.contains(e.target)
      if (!insidePanel && !onAnchor) onClose('outside')
    }
    document.addEventListener('keydown', onKeyDown)
    // capture fáze — ať se stihne dřív, než by klik samotný něco jiného spustil
    document.addEventListener('pointerdown', onPointerDown, true)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('pointerdown', onPointerDown, true)
    }
  }, [onClose, anchorRef])

  return (
    <div className="song-picker" ref={panelRef}>
      <SearchBar value={query} onChange={setQuery} />
      <div
        className="song-picker-list-wrap"
        ref={listWrapRef}
        onClick={(e) => {
          if (e.target.closest('a')) onClose('select')
        }}
      >
        {loading && <LoadingState label="Načítám písně…" />}
        {!loading && error && <ErrorState message="Seznam písní se nepodařilo načíst." />}
        {!loading && !error && items.length === 0 && (
          <EmptyState
            title={isSearching ? `Nic jsme nenašli pro „${query.trim()}“` : 'Ve zpěvníku zatím nic není'}
            description={isSearching ? 'Zkus jiný kód nebo část názvu.' : undefined}
          />
        )}
        {!loading && !error && items.length > 0 && (
          <SongList>
            {items.map((song) => (
              <SongRow
                key={song.id}
                song={song}
                href={hrefFor?.(song)}
                current={String(song.id) === String(currentSongId)}
              />
            ))}
          </SongList>
        )}
      </div>
    </div>
  )
}
