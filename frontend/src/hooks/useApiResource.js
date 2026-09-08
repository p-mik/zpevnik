import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

// Jeden objekt (detail písně, zpěvníku…) — `data` je `undefined`, dokud se
// nenačte poprvé.
export function useApiResource(path) {
  const [data, setData] = useState(undefined)
  const [error, setError] = useState(null)
  const requestIdRef = useRef(0)

  const load = useCallback(async () => {
    if (!path) return
    const requestId = ++requestIdRef.current
    setData(undefined)
    setError(null)
    try {
      const result = await api.get(path)
      if (requestId !== requestIdRef.current) return
      setData(result)
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
