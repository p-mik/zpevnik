import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import SearchBar, { parseSearchQuery } from '../components/SearchBar'
import SongRow, { SongList } from '../components/SongRow'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import EmptyState from '../components/EmptyState'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useInfiniteList } from '../hooks/useInfiniteList'
import './SongQuickPicker.css'

// Rozbalovací rychlý výběr písně — stejné hledání (kód/název) a nekonečný
// scroll jako hlavní seznam písní, jen v malém panelu u titulku čtečky.
// Výběr je normální odkaz (SongRow). Panel se po něm zavře výslovně
// (onClose('select')) — spolehnout se jen na to, že navigace panel "zboří",
// nejde: výběr právě otevřené písně URL nezmění a panel by zůstal viset.
// `anchorRef` = tlačítko, které panel otevírá. Pointerdown na něm se NESMÍ
// brát jako "klik mimo" — jinak by druhý klik na titulek panel nejdřív zavřel
// (pointerdown) a hned zas otevřel (click toggle), takže by nešel zavřít.
// `hrefFor(song)` = kam vede výběr (výchozí je čtečka, stage mode chce stage).
// `onClose(reason)` dostane 'outside' | 'escape' — stage mode podle toho
// pozná, že tap mimo panel má panel jen zavřít, a ne zároveň otočit stránku.
// `currentSongId` = právě otevřená píseň: po otevření se seznam donačte až
// k ní, nascrolluje na ni a zvýrazní ji, ať se nezačíná vždy od 101.
export default function SongQuickPicker({ onClose, anchorRef, hrefFor, currentSongId }) {
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebouncedValue(query, 250)
  const params = useMemo(() => parseSearchQuery(debouncedQuery), [debouncedQuery])
  const { items, loading, loadingMore, error, hasMore, loadMore } = useInfiniteList('/api/pisne/', params)

  const panelRef = useRef(null)
  const sentinelRef = useRef(null)
  const listWrapRef = useRef(null)
  const scrolledToCurrentRef = useRef(false)
  const isSearching = debouncedQuery.trim() !== ''

  // Seznam je stránkovaný — aktuální píseň může být až na další stránce,
  // tak se dotahuje, dokud se neobjeví (nebo dokud je co dotahovat). Jen
  // jednou po otevření a jen bez hledání: kdo hledá, chce vidět výsledky.
  useEffect(() => {
    if (scrolledToCurrentRef.current || currentSongId == null || isSearching || loading) return
    const found = items.some((song) => String(song.id) === String(currentSongId))
    if (!found) {
      if (hasMore && !loadingMore) loadMore()
      else if (!hasMore) scrolledToCurrentRef.current = true
      return
    }
    scrolledToCurrentRef.current = true
    const wrap = listWrapRef.current
    const row = wrap?.querySelector('.song-row-current')
    if (!wrap || !row) return
    const wrapRect = wrap.getBoundingClientRect()
    const rowRect = row.getBoundingClientRect()
    wrap.scrollTop += rowRect.top - wrapRect.top - (wrap.clientHeight - rowRect.height) / 2
  }, [items, loading, loadingMore, hasMore, loadMore, currentSongId, isSearching])

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
    const el = sentinelRef.current
    if (!el || !hasMore) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) loadMore()
      },
      { rootMargin: '200px' },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [hasMore, loadMore])

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
            title={isSearching ? `Nic jsme nenašli pro „${debouncedQuery.trim()}“` : 'Ve zpěvníku zatím nic není'}
            description={isSearching ? 'Zkus jiný kód nebo část názvu.' : undefined}
          />
        )}
        {!loading && !error && items.length > 0 && (
          <>
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
            {hasMore && <div ref={sentinelRef} aria-hidden="true" />}
          </>
        )}
      </div>
    </div>
  )
}
