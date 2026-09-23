import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import {
  PRAZDNY_ZAPIS,
  aplikujZmenuTaktuNaVyber,
  aplikujZmenuVychozihoTaktu,
  novaSekce,
  novaSekceBezRadku,
  novyRadek,
  novyTakt,
  odeberTaktZeSekce,
  pridejTaktDoRadku,
  rozdelRadekOdTaktu,
  rozdelSekciOdRadku,
  spojSeSPredchozi,
} from './akordovyModel'

const CHYBA_NACTENI = 'Akordový zápis se nepodařilo načíst.'
const CHYBA_ULOZENI = 'Akordový zápis se nepodařilo uložit.'

// Stejný vzor jako useAnotace: explicitní Uložit, "neuloženo" odvozené
// porovnáním s posledním uloženým stavem.
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

  // Volající (komponenta) MUSÍ napřed ověřit zpusobiZtratuZmenaVychozihoTaktu
  // a případně potvrdit u uživatele — tahle akce jen aplikuje.
  const nastavTakt = useCallback((novyDob, novaHodnota) => {
    setZapis((prev) => ({
      ...prev,
      takt: { dob: novyDob, hodnota: novaHodnota },
      sekce: aplikujZmenuVychozihoTaktu(prev.sekce, novyDob),
    }))
  }, [])

  const nastavTempo = useCallback((tempo) => {
    setZapis((prev) => ({ ...prev, tempo }))
  }, [])

  // --- sekce ---

  const pridejSekci = useCallback(() => {
    setZapis((prev) => ({ ...prev, sekce: [...prev.sekce, novaSekce(prev.takt.dob)] }))
  }, [])

  const pridejSekciBezRadku = useCallback(() => {
    setZapis((prev) => ({ ...prev, sekce: [...prev.sekce, novaSekceBezRadku()] }))
  }, [])

  const smazSekci = useCallback((sekceIdx) => {
    setZapis((prev) => ({ ...prev, sekce: prev.sekce.filter((_, i) => i !== sekceIdx) }))
  }, [])

  const nastavNazevSekce = useCallback((sekceIdx, text) => {
    setZapis((prev) => ({
      ...prev,
      sekce: prev.sekce.map((s, i) => (i === sekceIdx ? { ...s, nazev: text } : s)),
    }))
  }, [])

  // Validaci (repetice přes hranici dělení) dělá volající PŘED zavoláním
  // téhle akce — stejný vzor jako potvrzení u "Změnit takt" (viz
  // AkordovyMrizka.potvrdZmenuTaktu). Když by přesto přišel neplatný
  // požadavek, `rozdelSekciOdRadku` vrátí `{ok:false}` a tady se prostě
  // nic nezmění (žádný pád, jen tichý no-op).
  const rozdelSekci = useCallback((sekceIdx, radekIdx) => {
    setZapis((prev) => {
      const vysledek = rozdelSekciOdRadku(prev.sekce[sekceIdx], radekIdx)
      if (!vysledek.ok) return prev
      const noveSekce = [...prev.sekce]
      noveSekce.splice(sekceIdx, 1, vysledek.puvodni, vysledek.nova)
      return { ...prev, sekce: noveSekce }
    })
  }, [])

  const spojSePredchozi = useCallback((sekceIdx) => {
    setZapis((prev) => {
      if (sekceIdx <= 0 || sekceIdx >= prev.sekce.length) return prev
      const spojena = spojSeSPredchozi(prev.sekce[sekceIdx - 1], prev.sekce[sekceIdx])
      const noveSekce = [...prev.sekce]
      noveSekce.splice(sekceIdx - 1, 2, spojena)
      return { ...prev, sekce: noveSekce }
    })
  }, [])

  // --- řádky ---

  const vlozRadekPo = useCallback((sekceIdx, radekIdx) => {
    setZapis((prev) => ({
      ...prev,
      sekce: prev.sekce.map((s, i) => {
        if (i !== sekceIdx) return s
        const radky = [...s.radky]
        radky.splice(radekIdx + 1, 0, novyRadek(prev.takt.dob))
        return { ...s, radky }
      }),
    }))
  }, [])

  // Validaci (repetice přes hranici zalomení) dělá volající PŘED
  // zavoláním téhle akce — stejný vzor jako `rozdelSekci`. Neplatný
  // požadavek: `rozdelRadekOdTaktu` vrátí `{ok:false}`, tady se nic
  // nezmění (tichý no-op).
  const rozdelRadek = useCallback((sekceIdx, radekIdx, taktIdx) => {
    setZapis((prev) => {
      const vysledek = rozdelRadekOdTaktu(prev.sekce[sekceIdx], radekIdx, taktIdx)
      if (!vysledek.ok) return prev
      return {
        ...prev,
        sekce: prev.sekce.map((s, i) => (i === sekceIdx ? vysledek.sekce : s)),
      }
    })
  }, [])

  // --- takty a buňky ---

  const pridejTakt = useCallback((sekceIdx, radekIdx) => {
    setZapis((prev) => ({
      ...prev,
      sekce: prev.sekce.map((s, i) =>
        i === sekceIdx
          ? { ...s, radky: s.radky.map((r, ri) => (ri === radekIdx ? pridejTaktDoRadku(r, prev.takt.dob) : r)) }
          : s,
      ),
    }))
  }, [])

  const smazTakt = useCallback((sekceIdx, radekIdx, taktIdx) => {
    setZapis((prev) => ({
      ...prev,
      sekce: prev.sekce.map((s, i) => (i === sekceIdx ? odeberTaktZeSekce(s, radekIdx, taktIdx) : s)),
    }))
  }, [])

  const upravBunku = useCallback((sekceIdx, radekIdx, taktIdx, dobaIdx, text) => {
    setZapis((prev) => ({
      ...prev,
      sekce: prev.sekce.map((s, si) => {
        if (si !== sekceIdx) return s
        return {
          ...s,
          radky: s.radky.map((r, ri) => {
            if (ri !== radekIdx) return r
            return {
              ...r,
              takty: r.takty.map((t, ti) => {
                if (ti !== taktIdx) return t
                const bunky = [...t.bunky]
                bunky[dobaIdx] = text
                return { ...t, bunky }
              }),
            }
          }),
        }
      }),
    }))
  }, [])

  // --- "Změnit takt" na výběru — validace/potvrzení dělá volající ---

  const zmenTaktVyberu = useCallback((vyber, novyTakt) => {
    setZapis((prev) => aplikujZmenuTaktuNaVyber(prev, vyber, novyTakt))
  }, [])

  // --- repetice ---

  const pridejRepetici = useCallback((sekceIdx, od_taktu, do_taktu, krat) => {
    setZapis((prev) => ({
      ...prev,
      sekce: prev.sekce.map((s, i) =>
        i === sekceIdx ? { ...s, repetice: [...s.repetice, { od_taktu, do_taktu, krat }] } : s,
      ),
    }))
  }, [])

  const smazRepetici = useCallback((sekceIdx, repIdx) => {
    setZapis((prev) => ({
      ...prev,
      sekce: prev.sekce.map((s, i) =>
        i === sekceIdx ? { ...s, repetice: s.repetice.filter((_, j) => j !== repIdx) } : s,
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
    pridejSekci,
    pridejSekciBezRadku,
    smazSekci,
    nastavNazevSekce,
    rozdelSekci,
    spojSePredchozi,
    vlozRadekPo,
    rozdelRadek,
    pridejTakt,
    smazTakt,
    upravBunku,
    zmenTaktVyberu,
    pridejRepetici,
    smazRepetici,
    uloz,
  }
}

// Znovu-exportovat i konstruktor prázdné buňky/taktu pro komponenty (focus
// po vytvoření nové sekce apod.), ať netahají akordovyModel duplicitně.
export { novyTakt }
