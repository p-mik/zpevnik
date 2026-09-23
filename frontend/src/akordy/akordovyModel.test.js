import { describe, expect, test } from 'vitest'
import {
  duplikujSekci,
  globalniIndexTaktu,
  odeberTaktZeSekce,
  posunSekciVPoli,
  rozdelRadekOdTaktu,
  rozdelSekciOdRadku,
  spojRadekSPredchozim,
  spojSeSPredchozi,
  voltyVRadku,
  zkontrolujVyberProVoltu,
} from './akordovyModel'

// Pomocník: řádek se `n` takty výchozího taktu (obsah buněk je pro tyhle
// testy lhostejný, jen počet taktů se počítá).
function radek(n) {
  return { takty: Array.from({ length: n }, () => ({ bunky: [''] })) }
}

describe('posunSekciVPoli', () => {
  test('prohodí sekci s tou o jednu pozici nahoru (smer -1)', () => {
    const sekce = [{ nazev: 'A' }, { nazev: 'B' }, { nazev: 'C' }]
    const vysledek = posunSekciVPoli(sekce, 1, -1)
    expect(vysledek.map((s) => s.nazev)).toEqual(['B', 'A', 'C'])
  })

  test('prohodí sekci s tou o jednu pozici dolů (smer +1)', () => {
    const sekce = [{ nazev: 'A' }, { nazev: 'B' }, { nazev: 'C' }]
    const vysledek = posunSekciVPoli(sekce, 1, 1)
    expect(vysledek.map((s) => s.nazev)).toEqual(['A', 'C', 'B'])
  })

  test('mimo rozsah (první sekce nahoru) vrátí pole beze změny', () => {
    const sekce = [{ nazev: 'A' }, { nazev: 'B' }]
    const vysledek = posunSekciVPoli(sekce, 0, -1)
    expect(vysledek).toBe(sekce)
  })

  test('mimo rozsah (poslední sekce dolů) vrátí pole beze změny', () => {
    const sekce = [{ nazev: 'A' }, { nazev: 'B' }]
    const vysledek = posunSekciVPoli(sekce, 1, 1)
    expect(vysledek).toBe(sekce)
  })

  test('repetice sekce se přesunou spolu s ní, beze změny indexů', () => {
    const a = { nazev: 'A', repetice: [{ od_taktu: 0, do_taktu: 1, krat: 2 }] }
    const b = { nazev: 'B', repetice: [] }
    const vysledek = posunSekciVPoli([a, b], 0, 1)
    expect(vysledek).toEqual([b, a])
    expect(vysledek[1].repetice).toEqual([{ od_taktu: 0, do_taktu: 1, krat: 2 }])
  })
})

describe('duplikujSekci', () => {
  test('vloží kopii hned pod původní sekci, se stejným názvem', () => {
    const sekce = [
      { nazev: 'Sloka', radky: [radek(2)], repetice: [{ od_taktu: 0, do_taktu: 1, krat: 2 }] },
      { nazev: 'Refrén', radky: [radek(1)], repetice: [] },
    ]
    const vysledek = duplikujSekci(sekce, 0)
    expect(vysledek.length).toBe(3)
    expect(vysledek[0].nazev).toBe('Sloka')
    expect(vysledek[1].nazev).toBe('Sloka')
    expect(vysledek[1]).toEqual(vysledek[0])
    expect(vysledek[2].nazev).toBe('Refrén')
  })

  test('kopie je hluboká — úprava kopie nemutuje originál', () => {
    const sekce = [{ nazev: 'Sloka', radky: [radek(2)], repetice: [] }]
    const vysledek = duplikujSekci(sekce, 0)
    vysledek[1].radky[0].takty[0].bunky[0] = 'ZMĚNA'
    expect(sekce[0].radky[0].takty[0].bunky[0]).toBe('')
  })

  test('duplikace prostřední sekce vloží kopii hned za ni, ne na konec', () => {
    const sekce = [{ nazev: 'A', radky: [], repetice: [] }, { nazev: 'B', radky: [], repetice: [] }, { nazev: 'C', radky: [], repetice: [] }]
    const vysledek = duplikujSekci(sekce, 1)
    expect(vysledek.map((s) => s.nazev)).toEqual(['A', 'B', 'B', 'C'])
  })
})

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
    expect(vysledek.hlaska).toBe('Tady je repetice nebo volta přes více řádků, nejdřív ji zruš.')
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

  test('volta se rozdělí stejně jako repetice — dolní se přepočte, horní zůstane', () => {
    const sekce = {
      nazev: 'S',
      radky: [radek(2), radek(3), radek(1)],
      repetice: [],
      volty: [
        { cislo: 1, od_taktu: 0, do_taktu: 1 }, // horní část
        { cislo: 2, od_taktu: 3, do_taktu: 4 }, // dolní část (hranice=2)
      ],
    }
    const vysledek = rozdelSekciOdRadku(sekce, 1)
    expect(vysledek.ok).toBe(true)
    expect(vysledek.puvodni.volty).toEqual([{ cislo: 1, od_taktu: 0, do_taktu: 1 }])
    expect(vysledek.nova.volty).toEqual([{ cislo: 2, od_taktu: 1, do_taktu: 2 }])
  })

  test('volta přes hranici dělení rozdělení odmítne', () => {
    const sekce = {
      nazev: 'S',
      radky: [radek(2), radek(3)],
      repetice: [],
      volty: [{ cislo: 1, od_taktu: 1, do_taktu: 3 }], // hranice=2, přesahuje
    }
    const vysledek = rozdelSekciOdRadku(sekce, 1)
    expect(vysledek.ok).toBe(false)
    expect(vysledek.hlaska).toBe('Tady je repetice nebo volta přes více řádků, nejdřív ji zruš.')
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

  test('volta obsahující smazaný takt se zahodí, volta PO něm se přepočte, volta PŘED ním beze změny', () => {
    const sekce = {
      nazev: 'S',
      radky: [{ takty: [{ bunky: ['A'] }, { bunky: ['B'] }, { bunky: ['C'] }, { bunky: ['D'] }] }],
      repetice: [],
      volty: [
        { cislo: 1, od_taktu: 0, do_taktu: 0 }, // před smazaným taktem (index 1) - beze změny
        { cislo: 2, od_taktu: 1, do_taktu: 1 }, // OBSAHUJE smazaný takt - zahodí se
        { cislo: 3, od_taktu: 2, do_taktu: 3 }, // po smazaném taktu - posune se o 1
      ],
    }
    const vysledek = odeberTaktZeSekce(sekce, 0, 1)
    expect(vysledek.volty).toEqual([
      { cislo: 1, od_taktu: 0, do_taktu: 0 },
      { cislo: 3, od_taktu: 1, do_taktu: 2 },
    ])
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
    expect(vysledek.hlaska).toBe('Tady je repetice nebo volta přes více řádků, nejdřív ji zruš.')
  })

  test('volta přes místo zalomení split odmítne stejnou hláškou', () => {
    const sekce = {
      nazev: 'S',
      radky: [radek(4)],
      repetice: [],
      volty: [{ cislo: 1, od_taktu: 1, do_taktu: 2 }], // zasahuje přes hranici (taktIdx=2)
    }
    const vysledek = rozdelRadekOdTaktu(sekce, 0, 2)
    expect(vysledek.ok).toBe(false)
    expect(vysledek.hlaska).toBe('Tady je repetice nebo volta přes více řádků, nejdřív ji zruš.')
  })

  test('volta mimo místo zalomení split povolí, indexy beze změny', () => {
    const sekce = {
      nazev: 'S',
      radky: [radek(4)],
      repetice: [],
      volty: [{ cislo: 1, od_taktu: 0, do_taktu: 1 }],
    }
    const vysledek = rozdelRadekOdTaktu(sekce, 0, 2)
    expect(vysledek.ok).toBe(true)
    expect(vysledek.sekce.volty).toEqual(sekce.volty)
  })
})

describe('spojRadekSPredchozim', () => {
  test('připojí takty řádku na konec předchozího, řádek zmizí', () => {
    const sekce = { nazev: 'S', radky: [radek(2), radek(3), radek(1)], repetice: [] }
    const vysledek = spojRadekSPredchozim(sekce, 1)
    expect(vysledek.radky).toEqual([radek(5), radek(1)])
  })

  test('mimo rozsah (radekIdx <= 0, první řádek sekce) vrátí sekci beze změny', () => {
    const sekce = { nazev: 'S', radky: [radek(2), radek(3)], repetice: [] }
    const vysledek = spojRadekSPredchozim(sekce, 0)
    expect(vysledek).toBe(sekce)
  })

  test('globální index taktů v sekci se nemění -> repetice před i za místem spojení zůstávají beze změny', () => {
    // řádky: 2 takty, 3 takty, 1 takt -> spojíme 2. řádek (3 takty) do 1.
    const sekce = {
      nazev: 'S',
      radky: [radek(2), radek(3), radek(1)],
      repetice: [
        { od_taktu: 0, do_taktu: 1, krat: 2 }, // celá v prvním řádku
        { od_taktu: 5, do_taktu: 5, krat: 4 }, // celá ve třetím řádku (za místem spojení)
      ],
    }
    const vysledek = spojRadekSPredchozim(sekce, 1)
    expect(vysledek.radky).toEqual([radek(5), radek(1)])
    expect(vysledek.repetice).toEqual(sekce.repetice)
  })

  test('repetice přesahující PŘES místo spojení (na hranici dvou spojovaných řádků) zůstane platná beze změny', () => {
    // repetice na taktech 1-2 (0-based) - poslední takt 1. řádku + první
    // takt 2. řádku - spojení nemění pořadí taktů, takže zůstává validní
    // beze změny indexů (na rozdíl od rozdělení tohle NENÍ odmítnuto).
    const sekce = {
      nazev: 'S',
      radky: [radek(2), radek(3)],
      repetice: [{ od_taktu: 1, do_taktu: 2, krat: 2 }],
    }
    const vysledek = spojRadekSPredchozim(sekce, 1)
    expect(vysledek.repetice).toEqual(sekce.repetice)
    // a globální index taktu 2 (teď v jediném spojeném řádku) odkazuje
    // pořád na stejný takt jako před spojením.
    const globalniPred = globalniIndexTaktu(sekce, 1, 0) // 1. takt 2. řádku před spojením
    const globalniPo = globalniIndexTaktu(vysledek, 0, 2) // stejný takt, teď na indexu 2 spojeného řádku
    expect(globalniPo).toBe(globalniPred)
  })

  test('spojení je přesná inverze rozdělení (round-trip taktů i repetic)', () => {
    // řádky: 2, 3, 1 takt -> dělíme 2. řádek (takty 2,3,4) na taktIdx=2
    // (globálně takt 4) - repetice nesmí přes tohle místo přesahovat,
    // jinak by ji rozdelRadekOdTaktu odmítl (viz ten popis výš).
    const puvodniSekce = {
      nazev: 'Refrén',
      radky: [radek(2), radek(3), radek(1)],
      repetice: [
        { od_taktu: 0, do_taktu: 1, krat: 2 },
        { od_taktu: 4, do_taktu: 5, krat: 3 },
      ],
    }
    const rozdeleno = rozdelRadekOdTaktu(puvodniSekce, 1, 2)
    expect(rozdeleno.ok).toBe(true)
    const spojeno = spojRadekSPredchozim(rozdeleno.sekce, 2)
    expect(spojeno.radky).toEqual(puvodniSekce.radky)
    expect(spojeno.repetice).toEqual(puvodniSekce.repetice)
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

  test('volty aktuální sekce se přeindexují o počet taktů předchozí, volty předchozí beze změny', () => {
    const predchozi = { nazev: 'A', radky: [radek(2), radek(1)], repetice: [], volty: [{ cislo: 1, od_taktu: 0, do_taktu: 0 }] }
    const aktualni = { nazev: 'B', radky: [radek(2)], repetice: [], volty: [{ cislo: 2, od_taktu: 0, do_taktu: 1 }] }
    const spojena = spojSeSPredchozi(predchozi, aktualni)
    expect(spojena.volty).toEqual([
      { cislo: 1, od_taktu: 0, do_taktu: 0 },
      { cislo: 2, od_taktu: 3, do_taktu: 4 },
    ])
  })

  test('spojení je přesná inverze rozdělení i pro volty (round-trip)', () => {
    const puvodniSekce = {
      nazev: 'Refrén',
      radky: [radek(2), radek(3), radek(1)],
      repetice: [],
      volty: [
        { cislo: 1, od_taktu: 0, do_taktu: 1 },
        { cislo: 2, od_taktu: 3, do_taktu: 5 },
      ],
    }
    const rozdeleno = rozdelSekciOdRadku(puvodniSekce, 1)
    expect(rozdeleno.ok).toBe(true)
    const spojeno = spojSeSPredchozi(rozdeleno.puvodni, { ...rozdeleno.nova, nazev: 'Refrén' })
    expect(spojeno.volty).toEqual(puvodniSekce.volty)
  })
})

describe('zkontrolujVyberProVoltu', () => {
  function vyberCelehoTaktu(sekceIdx, radekIdx, taktIdx) {
    return { sekceIdx, radekIdx, bunkaIdxVRadku: taktIdx }
  }

  test('prázdný výběr odmítne', () => {
    const zapis = { sekce: [{ nazev: 'S', radky: [radek(4)], repetice: [], volty: [] }] }
    const vysledek = zkontrolujVyberProVoltu(zapis, [])
    expect(vysledek.ok).toBe(false)
    expect(vysledek.hlaska).toBe('Nejdřív vyber aspoň jeden takt.')
  })

  test('výběr přes víc sekcí odmítne', () => {
    const zapis = {
      sekce: [
        { nazev: 'A', radky: [radek(2)], repetice: [], volty: [] },
        { nazev: 'B', radky: [radek(2)], repetice: [], volty: [] },
      ],
    }
    const vyber = [vyberCelehoTaktu(0, 0, 0), vyberCelehoTaktu(1, 0, 0)]
    const vysledek = zkontrolujVyberProVoltu(zapis, vyber)
    expect(vysledek.ok).toBe(false)
    expect(vysledek.hlaska).toBe('Volta jen v rámci jedné sekce.')
  })

  test('výběr UVNITŘ repetice povolí', () => {
    const zapis = {
      sekce: [{ nazev: 'S', radky: [radek(4)], repetice: [{ od_taktu: 0, do_taktu: 3, krat: 2 }], volty: [] }],
    }
    const vyber = [vyberCelehoTaktu(0, 0, 2), vyberCelehoTaktu(0, 0, 3)]
    const vysledek = zkontrolujVyberProVoltu(zapis, vyber)
    expect(vysledek.ok).toBe(true)
    expect(vysledek.od_taktu).toBe(2)
    expect(vysledek.do_taktu).toBe(3)
  })

  test('výběr HNED ZA repeticí (bez mezery) povolí', () => {
    const zapis = {
      sekce: [{ nazev: 'S', radky: [radek(6)], repetice: [{ od_taktu: 0, do_taktu: 3, krat: 2 }], volty: [] }],
    }
    const vyber = [vyberCelehoTaktu(0, 0, 4), vyberCelehoTaktu(0, 0, 5)]
    const vysledek = zkontrolujVyberProVoltu(zapis, vyber)
    expect(vysledek.ok).toBe(true)
  })

  test('výběr ani uvnitř, ani hned za repeticí odmítne', () => {
    const zapis = {
      sekce: [{ nazev: 'S', radky: [radek(8)], repetice: [{ od_taktu: 0, do_taktu: 3, krat: 2 }], volty: [] }],
    }
    // mezera - takt 6 je AŽ za taktem 5, ne hned za repeticí (ta konci na 3)
    const vyber = [vyberCelehoTaktu(0, 0, 6)]
    const vysledek = zkontrolujVyberProVoltu(zapis, vyber)
    expect(vysledek.ok).toBe(false)
    expect(vysledek.hlaska).toBe('Volta musí ležet uvnitř repetice, nebo hned za ní.')
  })

  test('výběr bez jakékoliv repetice v sekci odmítne', () => {
    const zapis = { sekce: [{ nazev: 'S', radky: [radek(4)], repetice: [], volty: [] }] }
    const vyber = [vyberCelehoTaktu(0, 0, 0)]
    const vysledek = zkontrolujVyberProVoltu(zapis, vyber)
    expect(vysledek.ok).toBe(false)
    expect(vysledek.hlaska).toBe('Volta musí ležet uvnitř repetice, nebo hned za ní.')
  })

  test('překryv s existující voltou odmítne', () => {
    const zapis = {
      sekce: [
        {
          nazev: 'S',
          radky: [radek(4)],
          repetice: [{ od_taktu: 0, do_taktu: 3, krat: 2 }],
          volty: [{ cislo: 1, od_taktu: 2, do_taktu: 3 }],
        },
      ],
    }
    const vyber = [vyberCelehoTaktu(0, 0, 3)]
    const vysledek = zkontrolujVyberProVoltu(zapis, vyber)
    expect(vysledek.ok).toBe(false)
    expect(vysledek.hlaska).toBe('Tenhle úsek se překrývá s existující voltou.')
  })
})

describe('voltyVRadku', () => {
  test('najde jen volty, co daný řádek zasahují, s lokálními indexy', () => {
    const sekce = {
      radky: [radek(4), radek(4)],
      volty: [
        { cislo: 1, od_taktu: 2, do_taktu: 3 }, // v prvním řádku
        { cislo: 2, od_taktu: 5, do_taktu: 5 }, // v druhém řádku
      ],
    }
    const prvniRadek = voltyVRadku(sekce, 0)
    expect(prvniRadek.length).toBe(1)
    expect(prvniRadek[0]).toMatchObject({ odTaktLokalni: 2, doTaktLokalni: 3, kresliZacatek: true, kresliKonec: true })

    const druhyRadek = voltyVRadku(sekce, 1)
    expect(druhyRadek.length).toBe(1)
    expect(druhyRadek[0]).toMatchObject({ odTaktLokalni: 1, doTaktLokalni: 1, kresliZacatek: true, kresliKonec: true })
  })

  test('volta přes víc řádků: kresliZacatek/kresliKonec jen na řádku, kde skutečně začíná/končí', () => {
    const sekce = {
      radky: [radek(4), radek(2)],
      volty: [{ cislo: 1, od_taktu: 3, do_taktu: 5 }], // takt 3 (poslední v radku0) az takt5 (v radku1)
    }
    const prvniRadek = voltyVRadku(sekce, 0)
    expect(prvniRadek[0]).toMatchObject({ odTaktLokalni: 3, doTaktLokalni: 3, kresliZacatek: true, kresliKonec: false })

    const druhyRadek = voltyVRadku(sekce, 1)
    expect(druhyRadek[0]).toMatchObject({ odTaktLokalni: 0, doTaktLokalni: 1, kresliZacatek: false, kresliKonec: true })
  })
})
