import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import { extractErrorMessage } from '../api/errors'

const CHYBA_NACTENI = 'Poznámky se nepodařilo načíst.'
const CHYBA_ULOZENI = 'Poznámky se nepodařilo uložit.'

// Poznámky patří ke konkrétní VERZI, ne k písni — pozice platí nad konkrétním
// PDF. Při přepnutí verze se proto načtou jiné (a to i prázdné).
//
// Ukládá se výslovně, celé pole naráz. Žádný autosave při každém písmenu:
// jednak by to na pódiu znamenalo desítky requestů, jednak se poznámka běžně
// rozepíše a promyslí — a mezistav není co posílat.
export function useAnotace(verzeId) {
  const [objekty, setObjekty] = useState([])
  const [ulozeno, setUlozeno] = useState('[]')
  const [nacitam, setNacitam] = useState(false)
  const [ukladam, setUkladam] = useState(false)
  const [chyba, setChyba] = useState(null)

  useEffect(() => {
    if (!verzeId) {
      setObjekty([])
      setUlozeno('[]')
      return undefined
    }
    let zruseno = false
    setNacitam(true)
    setChyba(null)
    api
      .get(`/api/verze-pisni/${verzeId}/anotace/`)
      .then((odpoved) => {
        if (zruseno) return
        const data = odpoved?.data ?? []
        setObjekty(data)
        setUlozeno(JSON.stringify(data))
      })
      .catch((err) => {
        if (!zruseno) setChyba(extractErrorMessage(err, CHYBA_NACTENI))
      })
      .finally(() => {
        if (!zruseno) setNacitam(false)
      })
    return () => {
      zruseno = true
    }
  }, [verzeId])

  // Odvozeno, ne v samostatném stavu — jeden zdroj pravdy, žádná cesta, jak
  // by se "neuloženo" rozešlo se skutečným obsahem.
  const zmeneno = useMemo(() => JSON.stringify(objekty) !== ulozeno, [objekty, ulozeno])

  const pridej = useCallback((objekt) => {
    setObjekty((prev) => [...prev, objekt])
  }, [])

  const zmen = useCallback((id, zmeny) => {
    setObjekty((prev) => prev.map((o) => (o.id === id ? { ...o, ...zmeny } : o)))
  }, [])

  const smaz = useCallback((id) => {
    setObjekty((prev) => prev.filter((o) => o.id !== id))
  }, [])

  const uloz = useCallback(async () => {
    if (!verzeId) return false
    setUkladam(true)
    setChyba(null)
    try {
      const odpoved = await api.put(`/api/verze-pisni/${verzeId}/anotace/`, {
        data: objekty,
      })
      // Uloží se to, co vrátil server — po uložení tak klient drží přesně ta
      // data, která v databázi opravdu jsou (včetně doplněných výchozích hodnot).
      const data = odpoved?.data ?? objekty
      setObjekty(data)
      setUlozeno(JSON.stringify(data))
      return true
    } catch (err) {
      setChyba(extractErrorMessage(err, CHYBA_ULOZENI))
      return false
    } finally {
      setUkladam(false)
    }
  }, [verzeId, objekty])

  return { objekty, nacitam, ukladam, chyba, zmeneno, pridej, zmen, smaz, uloz }
}

// Nedopsané poznámky se ztrácejí špatně — zvlášť když se appka na pódiu
// zavírá ve spěchu. Platí jen pro zavření/obnovení karty; přechod na jinou
// píseň uvnitř appky tohle neodchytí (prohlížeč o něm neví).
export function useVarovaniPriOdchodu(aktivni) {
  useEffect(() => {
    if (!aktivni) return undefined
    function pred(e) {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', pred)
    return () => window.removeEventListener('beforeunload', pred)
  }, [aktivni])
}
