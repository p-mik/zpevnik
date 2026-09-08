import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

// Stáhne všechny stránky a vrátí jedno pole — pro složky/zpěvníky, kde
// backend zatím neumí `?rodic=`/`?slozka=` filtr (viz README poznámka),
// takže se strom staví po straně klienta. V pořádku při desítkách položek,
// ne stovkách.
export function useAllPages(path) {
  const [data, setData] = useState(undefined)
  const [error, setError] = useState(null)
  const requestIdRef = useRef(0)

  const load = useCallback(async () => {
    const requestId = ++requestIdRef.current
    setData(undefined)
    setError(null)
    try {
      let items = []
      let url = path
      while (url) {
        const page = await api.get(url)
        items = items.concat(page.results)
        url = page.next ? new URL(page.next).pathname + new URL(page.next).search : null
      }
      if (requestId !== requestIdRef.current) return
      setData(items)
    } catch (err) {
      if (requestId !== requestIdRef.current) return
      setError(err)
    }
  }, [path])

  useEffect(() => {
    load()
  }, [load])

  return { data, loading: data === undefined && !error, error, reload: load }
}
