import { useEffect, useMemo, useRef, useState } from 'react'
import SearchBar, { parseSearchQuery } from '../components/SearchBar'
import SongRow, { SongList } from '../components/SongRow'
import LoadingState from '../components/LoadingState'
import EmptyState from '../components/EmptyState'
import ErrorState from '../components/ErrorState'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useInfiniteList } from '../hooks/useInfiniteList'

export default function SongListPage() {
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebouncedValue(query, 250)
  const params = useMemo(() => parseSearchQuery(debouncedQuery), [debouncedQuery])

  const { items, loading, loadingMore, error, hasMore, loadMore, reload } = useInfiniteList(
    '/api/pisne/',
    params,
  )

  const sentinelRef = useRef(null)

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

  const isSearching = debouncedQuery.trim() !== ''

  return (
    <div>
      <SearchBar value={query} onChange={setQuery} />

      {loading && <LoadingState label="Načítám písně…" />}

      {!loading && error && (
        <ErrorState message="Seznam písní se nepodařilo načíst." onRetry={reload} />
      )}

      {!loading && !error && items.length === 0 && isSearching && (
        <EmptyState
          title={`Nic jsme nenašli pro „${debouncedQuery.trim()}“`}
          description="Zkus jiný kód nebo část názvu."
          actionLabel="Vymazat hledání"
          onAction={() => setQuery('')}
        />
      )}

      {!loading && !error && items.length === 0 && !isSearching && (
        <EmptyState
          title="Ve zpěvníku zatím nic není"
          description="Písně se přidávají přes administraci — tam se nahrávají i noty."
          actionLabel="Otevřít administraci"
          actionHref="/admin/"
        />
      )}

      {!loading && !error && items.length > 0 && (
        <>
          <SongList>
            {items.map((song) => (
              <SongRow key={song.id} song={song} />
            ))}
          </SongList>
          {hasMore && <div ref={sentinelRef} aria-hidden="true" />}
          {loadingMore && <LoadingState label="Načítám další…" />}
        </>
      )}
    </div>
  )
}
