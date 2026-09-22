import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import {
  PRAZDNY_ZAPIS,
  novyRadek,
  odeberTakt,
  preskladejNaNovyTakt,
  pridejTakt as pridejTaktDoRadku,
} from './akordovyModel'

const CHYBA_NACTENI = 'Akordový zápis se nepodařilo načíst.'
const CHYBA_ULOZENI = 'Akordový zápis se nepodařilo uložit.'

// Stejný vzor jako useAnotace: explicitní Uložit, "neuloženo" odvozené
// porovnáním s posledním uloženým stavem (žádný autosave při každém
// stisku klávesy — psaní akordu je rozepsaná akce, ne hotová hodnota).
export function useAkordovyEditor(verzeId) {
  const [zapis, setZapis] = useState(PRAZDNY_ZAPIS)
  const [ulozeno, setUlozeno] = useState(JSON.stringify(PRAZDNY_ZAPIS))
  const [nacitam, setNacitam] = useState(true)
  const [ukladam, setUkladam] = useState(false)
  const [chyba, setChyba] = useState(null)
  const [pocetAnotaciKtereMohlyUjet, setPocetAnotaciKtereMohlyUjet] = useState(null)

  useEffect(() => {
    if (!verzeId) {
      setNacitam(false)
      return undefined
    }
    let zruseno = false
    setNacitam(true)
    setChyba(null)
    api
      .get(`/api/verze-pisni/${verzeId}/akordy/`)
      .then((data) => {
        if (zruseno) return
        const nacteny = data && data.schema ? data : PRAZDNY_ZAPIS
        setZapis(nacteny)
        setUlozeno(JSON.stringify(nacteny))
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

  const zmeneno = useMemo(() => JSON.stringify(zapis) !== ulozeno, [zapis, ulozeno])
  const dob = zapis.takt.dob

  // --- takt / tempo ---

  const nastavTakt = useCallback((novyDob, novaHodnota) => {
    setZapis((prev) => ({
      ...prev,
      takt: { dob: novyDob, hodnota: novaHodnota },
      radky: preskladejNaNovyTakt(prev.radky, novyDob),
    }))
  }, [])

  const nastavTempo = useCallback((tempo) => {
    setZapis((prev) => ({ ...prev, tempo }))
  }, [])

  // --- řádky ---

  const pridejRadekNaKonec = useCallback(() => {
    setZapis((prev) => ({ ...prev, radky: [...prev.radky, novyRadek(prev.takt.dob)] }))
  }, [])

  const vlozRadekPo = useCallback((indexRadku) => {
    setZapis((prev) => {
      const radky = [...prev.radky]
      radky.splice(indexRadku + 1, 0, novyRadek(prev.takt.dob))
      return { ...prev, radky }
    })
  }, [])

  const smazRadek = useCallback((indexRadku) => {
    setZapis((prev) => ({ ...prev, radky: prev.radky.filter((_, i) => i !== indexRadku) }))
  }, [])

  const nastavSekci = useCallback((indexRadku, text) => {
    setZapis((prev) => ({
      ...prev,
      radky: prev.radky.map((r, i) => (i === indexRadku ? { ...r, sekce: text } : r)),
    }))
  }, [])

  // --- takty a buňky ---

  const pridejTakt = useCallback((indexRadku) => {
    setZapis((prev) => ({
      ...prev,
      radky: prev.radky.map((r, i) => (i === indexRadku ? pridejTaktDoRadku(r, prev.takt.dob) : r)),
    }))
  }, [])

  const smazTakt = useCallback((indexRadku, indexTaktu) => {
    setZapis((prev) => ({
      ...prev,
      radky: prev.radky.map((r, i) => (i === indexRadku ? odeberTakt(r, indexTaktu, prev.takt.dob) : r)),
    }))
  }, [])

  const upravBunku = useCallback((indexRadku, indexBunky, text) => {
    setZapis((prev) => ({
      ...prev,
      radky: prev.radky.map((r, i) => {
        if (i !== indexRadku) return r
        const bunky = [...r.bunky]
        bunky[indexBunky] = text
        return { ...r, bunky }
      }),
    }))
  }, [])

  // --- repetice ---

  const pridejRepetici = useCallback((indexRadku, od_takt, do_takt, krat) => {
    setZapis((prev) => ({
      ...prev,
      radky: prev.radky.map((r, i) =>
        i === indexRadku ? { ...r, repetice: [...r.repetice, { od_takt, do_takt, krat }] } : r,
      ),
    }))
  }, [])

  const smazRepetici = useCallback((indexRadku, indexRepetice) => {
    setZapis((prev) => ({
      ...prev,
      radky: prev.radky.map((r, i) =>
        i === indexRadku ? { ...r, repetice: r.repetice.filter((_, j) => j !== indexRepetice) } : r,
      ),
    }))
  }, [])

  // --- ukládání ---

  const uloz = useCallback(async () => {
    if (!verzeId) return false
    setUkladam(true)
    setChyba(null)
    try {
      const odpoved = await api.put(`/api/verze-pisni/${verzeId}/akordy/`, zapis)
      const data = odpoved?.akordy ?? zapis
      setZapis(data)
      setUlozeno(JSON.stringify(data))
      setPocetAnotaciKtereMohlyUjet(odpoved?.pocet_anotaci_ktere_mohly_ujet ?? 0)
      return true
    } catch (err) {
      setChyba(extractErrorMessage(err, CHYBA_ULOZENI))
      return false
    } finally {
      setUkladam(false)
    }
  }, [verzeId, zapis])

  return {
    zapis,
    dob,
    nacitam,
    ukladam,
    chyba,
    zmeneno,
    pocetAnotaciKtereMohlyUjet,
    nastavTakt,
    nastavTempo,
    pridejRadekNaKonec,
    vlozRadekPo,
    smazRadek,
    nastavSekci,
    pridejTakt,
    smazTakt,
    upravBunku,
    pridejRepetici,
    smazRepetici,
    uloz,
  }
}
