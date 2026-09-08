import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

// Stránkovaný seznam s dotahováním dalších stránek — stovky písní se
// nevykreslí najednou, načtou se, jen když se na ně doscrolluje.
export function useInfiniteList(path, params) {
  const paramsKey = JSON.stringify(params || {})
  const [items, setItems] = useState([])
  const [nextUrl, setNextUrl] = useState(null)
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState(null)
  const requestIdRef = useRef(0)

  const load = useCallback(async () => {
    const requestId = ++requestIdRef.current
    setLoading(true)
    setError(null)
    try {
      const qs = new URLSearchParams(JSON.parse(paramsKey)).toString()
      const url = qs ? `${path}?${qs}` : path
      const data = await api.get(url)
      if (requestId !== requestIdRef.current) return // odpověď na zastaralý dotaz
      setItems(data.results)
      setNextUrl(data.next)
      setCount(data.count)
    } catch (err) {
      if (requestId !== requestIdRef.current) return
      setError(err)
    } finally {
      if (requestId === requestIdRef.current) setLoading(false)
    }
  }, [path, paramsKey])

  useEffect(() => {
    load()
  }, [load])

  const loadMore = useCallback(async () => {
    if (!nextUrl || loadingMore) return
    setLoadingMore(true)
    try {
      // `next` je absolutní URL z DRF — použije se jen cesta, ať request jde
      // pořád na stejný origin (a v dev módu přes Vite proxy).
      const relative = new URL(nextUrl).pathname + new URL(nextUrl).search
      const data = await api.get(relative)
      setItems((prev) => [...prev, ...data.results])
      setNextUrl(data.next)
    } catch (err) {
      setError(err)
    } finally {
      setLoadingMore(false)
    }
  }, [nextUrl, loadingMore])

  return { items, count, loading, loadingMore, error, hasMore: Boolean(nextUrl), loadMore, reload: load }
}
