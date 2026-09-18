import { useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'

const KLIC_POSLEDNI = 'zpevnik:posledni-zpevnik'

function nactiPosledni() {
  try {
    return sessionStorage.getItem(KLIC_POSLEDNI)
  } catch {
    return null
  }
}

function ulozPosledni(zpevnikId) {
  try {
    sessionStorage.setItem(KLIC_POSLEDNI, String(zpevnikId))
  } catch {
    // soukromý režim / zakázané úložiště — kontext prostě nepřežije mezi
    // písněmi, appka na to nespoléhá jako na nutnost
  }
}

// Čtečka a stage mode musí VŽDY vědět, ve kterém zpěvníku jsou — kód i
// pořadí Předchozí/Další existují jen v rámci zpěvníku (viz PolozkaZpevniku),
// takže bez kontextu by appka musela buď lhát, nebo mlčet. Tenhle hook
// dopočítá `?z=` v URL, když chybí nebo neodpovídá téhle písni:
//  - píseň je v jednom zpěvníku -> ten se použije rovnou
//  - ve víc, a jeden z nich je ten použitý naposled v týhle relaci -> ten
//    (ať se uživatel neptá pokaždé, viz zadání)
//  - ve víc, a žádný takový není -> `potrebaVolby: true`, appka musí
//    nechat uživatele vybrat (viz ZpevnikVolba)
//  - v žádném (píseň bez jediného zařazení) -> žádný kontext; to je
//    degenerovaný případ mimo návrhové pravidlo "vždy pod zpěvníkem",
//    čtečka pak jede dál bez kódu a bez navigace v rámci zpěvníku
// Jednou zjištěný kontext se zapíše do URL (replace, ne push — ať
// Předchozí/Další v historii prohlížeče nevytváří zbytečné kroky navíc).
export function useZpevnikKontext(song) {
  const [searchParams, setSearchParams] = useSearchParams()
  const zUrl = searchParams.get('z')
  const zarazeni = useMemo(() => song?.zarazeni || [], [song])

  const zUrlPlatne = Boolean(zUrl) && zarazeni.some((z) => String(z.zpevnik) === String(zUrl))
  const posledni = !zUrlPlatne ? nactiPosledni() : null
  const posledniPlatny =
    !zUrlPlatne && posledni && zarazeni.some((z) => String(z.zpevnik) === String(posledni))
      ? posledni
      : null

  const zpevnikId = useMemo(() => {
    if (zUrlPlatne) return zUrl
    if (posledniPlatny) return posledniPlatny
    if (zarazeni.length === 1) return String(zarazeni[0].zpevnik)
    return null
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zUrlPlatne, zUrl, posledniPlatny, zarazeni])

  const potrebaVolby = !zpevnikId && zarazeni.length > 1

  // Zápis do URL a zapamatování — jako vedlejší efekt, ne při renderu.
  useEffect(() => {
    if (!zpevnikId) return
    ulozPosledni(zpevnikId)
    if (zpevnikId !== zUrl) {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.set('z', zpevnikId)
          return next
        },
        { replace: true },
      )
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zpevnikId, zUrl])

  function zvolZpevnik(id) {
    ulozPosledni(id)
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      next.set('z', String(id))
      return next
    })
  }

  return { zpevnikId, potrebaVolby, volby: zarazeni, zvolZpevnik }
}
