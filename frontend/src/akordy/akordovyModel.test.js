import { describe, expect, test } from 'vitest'
import { odeberTaktZeSekce, rozdelRadekOdTaktu, rozdelSekciOdRadku, spojSeSPredchozi } from './akordovyModel'

// Pomocník: řádek se `n` takty výchozího taktu (obsah buněk je pro tyhle
// testy lhostejný, jen počet taktů se počítá).
function radek(n) {
  return { takty: Array.from({ length: n }, () => ({ bunky: [''] })) }
}

describe('rozdelSekciOdRadku', () => {
  test('rozdělí řádky na horní a dolní část přesně podle radekIdx', () => {
    const sekce = {
      nazev: 'Sloka',
      radky: [radek(2), radek(3), radek(1)],
      repetice: [],
    }
    const vysledek = rozdelSekciOdRadku(sekce, 1)
    expect(vysledek.ok).toBe(true)
    expect(vysledek.puvodni.radky).toEqual([radek(2)])
    expect(vysledek.puvodni.nazev).toBe('Sloka')
    expect(vysledek.nova.radky).toEqual([radek(3), radek(1)])
    expect(vysledek.nova.nazev).toBe('') // nová sekce nemá název, focus jde tam
  })

  test('repetice celá v horní části zůstane beze změny indexů', () => {
    // řádky: 2 takty, 3 takty, 1 takt -> hranice dělení (radekIdx=1) = takt 2
    const sekce = {
      nazev: 'S',
      radky: [radek(2), radek(3), radek(1)],
      repetice: [{ od_taktu: 0, do_taktu: 1, krat: 2 }], // celá v prvním řádku (takty 0-1)
    }
    const vysledek = rozdelSekciOdRadku(sekce, 1)
    expect(vysledek.ok).toBe(true)
    expect(vysledek.puvodni.repetice).toEqual([{ od_taktu: 0, do_taktu: 1, krat: 2 }])
    expect(vysledek.nova.repetice).toEqual([])
  })

  test('repetice celá v dolní části se přesune s přepočtenými indexy', () => {
    // hranice = takt 2 (po prvním řádku o 2 taktech); repetice na taktech 3-4
    // (druhý a třetí takt DRUHÉHO řádku) -> v nové sekci by měla být 1-2
    const sekce = {
      nazev: 'S',
      radky: [radek(2), radek(3), radek(1)],
      repetice: [{ od_taktu: 3, do_taktu: 4, krat: 3 }],
    }
    const vysledek = rozdelSekciOdRadku(sekce, 1)
    expect(vysledek.ok).toBe(true)
    expect(vysledek.puvodni.repetice).toEqual([])
    expect(vysledek.nova.repetice).toEqual([{ od_taktu: 1, do_taktu: 2, krat: 3 }])
  })

  test('repetice přesně na hranici (končí posledním taktem horní části) zůstane nahoře', () => {
    const sekce = {
      nazev: 'S',
      radky: [radek(2), radek(2)],
      repetice: [{ od_taktu: 0, do_taktu: 1, krat: 2 }], // hranice = 2, do_taktu=1 < 2
    }
    const vysledek = rozdelSekciOdRadku(sekce, 1)
    expect(vysledek.ok).toBe(true)
    expect(vysledek.puvodni.repetice).toEqual([{ od_taktu: 0, do_taktu: 1, krat: 2 }])
  })

  test('repetice přes hranici dělení rozdělení odmítne', () => {
    // hranice = takt 2; repetice 1-3 zasahuje do obou částí
    const sekce = {
      nazev: 'S',
      radky: [radek(2), radek(3)],
      repetice: [{ od_taktu: 1, do_taktu: 3, krat: 2 }],
    }
    const vysledek = rozdelSekciOdRadku(sekce, 1)
    expect(vysledek.ok).toBe(false)
    expect(vysledek.hlaska).toBe('Tady je repetice přes více řádků, nejdřív ji zruš.')
  })

  test('víc repetic - jedna nahoře, jedna dole, obě se správně rozdělí', () => {
    const sekce = {
      nazev: 'S',
      radky: [radek(2), radek(2), radek(2)],
      repetice: [
        { od_taktu: 0, do_taktu: 1, krat: 2 }, // celá v prvním řádku (horní část)
        { od_taktu: 2, do_taktu: 3, krat: 3 }, // celá ve druhém řádku (dolní část)
      ],
    }
    const vysledek = rozdelSekciOdRadku(sekce, 1)
    expect(vysledek.ok).toBe(true)
    expect(vysledek.puvodni.repetice).toEqual([{ od_taktu: 0, do_taktu: 1, krat: 2 }])
    expect(vysledek.nova.repetice).toEqual([{ od_taktu: 0, do_taktu: 1, krat: 3 }])
  })
})

describe('odeberTaktZeSekce', () => {
  test('smazání posledního taktu jediného řádku nechá sekci bez řádků (ne reset na prázdný takt)', () => {
    const sekce = { nazev: 'S', radky: [{ takty: [{ bunky: ['C'] }] }], repetice: [] }
    const vysledek = odeberTaktZeSekce(sekce, 0, 0)
    expect(vysledek.radky).toEqual([])
  })

  test('repetice na jediném taktu se smaže spolu s ním, když sekci nezbydou řádky', () => {
    const sekce = {
      nazev: 'S',
      radky: [{ takty: [{ bunky: ['C'] }] }],
      repetice: [{ od_taktu: 0, do_taktu: 0, krat: 2 }],
    }
    const vysledek = odeberTaktZeSekce(sekce, 0, 0)
    expect(vysledek.radky).toEqual([])
    expect(vysledek.repetice).toEqual([])
  })

  test('smazání posledního taktu posledního řádku, když sekce má víc řádků, jen smaže ten řádek (beze změny)', () => {
    const sekce = {
      nazev: 'S',
      radky: [{ takty: [{ bunky: ['C'] }, { bunky: ['D'] }] }, { takty: [{ bunky: ['E'] }] }],
      repetice: [],
    }
    const vysledek = odeberTaktZeSekce(sekce, 1, 0)
    expect(vysledek.radky).toEqual([{ takty: [{ bunky: ['C'] }, { bunky: ['D'] }] }])
  })

  test('smazání jednoho z víc taktů v řádku jen odebere ten takt, řádek zůstane', () => {
    const sekce = { nazev: 'S', radky: [{ takty: [{ bunky: ['C'] }, { bunky: ['D'] }] }], repetice: [] }
    const vysledek = odeberTaktZeSekce(sekce, 0, 0)
    expect(vysledek.radky).toEqual([{ takty: [{ bunky: ['D'] }] }])
  })
})

describe('rozdelRadekOdTaktu', () => {
  test('přesune takty od taktIdx do nového řádku hned za původním', () => {
    const sekce = { nazev: 'S', radky: [radek(2), radek(4), radek(1)], repetice: [] }
    const vysledek = rozdelRadekOdTaktu(sekce, 1, 2)
    expect(vysledek.ok).toBe(true)
    expect(vysledek.sekce.radky).toEqual([radek(2), radek(2), radek(2), radek(1)])
  })

  test('sousední řádky (mimo ten dělený) zůstanou beze změny', () => {
    const sekce = { nazev: 'S', radky: [radek(3), radek(4)], repetice: [] }
    const vysledek = rozdelRadekOdTaktu(sekce, 1, 1)
    expect(vysledek.ok).toBe(true)
    expect(vysledek.sekce.radky[0]).toEqual(radek(3))
    expect(vysledek.sekce.radky[1]).toEqual(radek(1))
    expect(vysledek.sekce.radky[2]).toEqual(radek(3))
  })

  test('globální pořadí taktů v sekci se nemění -> repetice indexy zůstávají stejné na obou stranách', () => {
    // řádky: 2 takty, 4 takty -> dělíme druhý řádek na taktIdx=2 (globálně takt 4)
    const sekce = {
      nazev: 'S',
      radky: [radek(2), radek(4)],
      repetice: [
        { od_taktu: 0, do_taktu: 1, krat: 2 }, // celá před hranicí (první řádek)
        { od_taktu: 4, do_taktu: 5, krat: 3 }, // celá za hranicí (nový řádek)
      ],
    }
    const vysledek = rozdelRadekOdTaktu(sekce, 1, 2)
    expect(vysledek.ok).toBe(true)
    // na rozdíl od rozdelSekciOdRadku se tady indexy NEPŘEPOČÍTÁVAJÍ -
    // řádkové zalomení nemění pořadí ani počet taktů v sekci.
    expect(vysledek.sekce.repetice).toEqual(sekce.repetice)
  })

  test('repetice přesně končící před hranicí (do_taktu = hranice-1) split povolí', () => {
    const sekce = {
      nazev: 'S',
      radky: [radek(4)],
      repetice: [{ od_taktu: 0, do_taktu: 1, krat: 2 }], // konci v taktu 1, hranice=2
    }
    const vysledek = rozdelRadekOdTaktu(sekce, 0, 2)
    expect(vysledek.ok).toBe(true)
  })

  test('repetice přes místo zalomení split odmítne se stejnou hláškou jako u sekce', () => {
    const sekce = {
      nazev: 'S',
      radky: [radek(4)],
      repetice: [{ od_taktu: 1, do_taktu: 2, krat: 2 }], // zasahuje přes hranici (taktIdx=2)
    }
    const vysledek = rozdelRadekOdTaktu(sekce, 0, 2)
    expect(vysledek.ok).toBe(false)
    expect(vysledek.hlaska).toBe('Tady je repetice přes více řádků, nejdřív ji zruš.')
  })
})

describe('spojSeSPredchozi', () => {
  test('spojí řádky obou sekcí, název vyhrává předchozí', () => {
    const predchozi = { nazev: 'Sloka', radky: [radek(2)], repetice: [] }
    const aktualni = { nazev: 'Zahodit', radky: [radek(3)], repetice: [] }
    const spojena = spojSeSPredchozi(predchozi, aktualni)
    expect(spojena.nazev).toBe('Sloka')
    expect(spojena.radky).toEqual([radek(2), radek(3)])
  })

  test('repetice aktuální sekce se přeindexují o počet taktů předchozí', () => {
    const predchozi = { nazev: 'A', radky: [radek(2), radek(1)], repetice: [{ od_taktu: 0, do_taktu: 1, krat: 2 }] }
    const aktualni = { nazev: 'B', radky: [radek(2)], repetice: [{ od_taktu: 0, do_taktu: 1, krat: 4 }] }
    const spojena = spojSeSPredchozi(predchozi, aktualni)
    // predchozi ma 3 takty celkem -> repetice z aktualni se posune o 3
    expect(spojena.repetice).toEqual([
      { od_taktu: 0, do_taktu: 1, krat: 2 },
      { od_taktu: 3, do_taktu: 4, krat: 4 },
    ])
  })

  test('spojení je přesná inverze rozdělení (round-trip repetice indexů)', () => {
    const puvodniSekce = {
      nazev: 'Refrén',
      radky: [radek(2), radek(3), radek(1)],
      repetice: [
        { od_taktu: 0, do_taktu: 1, krat: 2 },
        { od_taktu: 3, do_taktu: 5, krat: 3 },
      ],
    }
    const rozdeleno = rozdelSekciOdRadku(puvodniSekce, 1)
    expect(rozdeleno.ok).toBe(true)
    const spojeno = spojSeSPredchozi(rozdeleno.puvodni, { ...rozdeleno.nova, nazev: 'Refrén' })
    expect(spojeno.radky).toEqual(puvodniSekce.radky)
    expect(spojeno.repetice).toEqual(puvodniSekce.repetice)
  })
})
