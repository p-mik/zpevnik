// Čistá logika akordového zápisu, schéma 2 (viz
// PC_zpevnik_akordovy_zapis_upravy.md) — žádné React, žádné API, jen
// transformace nad daty. Zrcadlí schéma, které ověřuje server
// (AkordovyZapisSerializer): sekce[] -> radky[] -> takty[] -> bunky[].
// `takty[].takt` je VOLITELNÝ přepis výchozího taktu dokumentu. `repetice`
// žije na SEKCI a indexuje takty přes VŠECHNY její řádky (0-based,
// `do_taktu` včetně) — repetice smí přes víc řádků JEDNÉ sekce, ne přes
// sekce.

export const PRAZDNY_ZAPIS = { schema: 2, takt: { dob: 4, hodnota: 4 }, tempo: null, sekce: [] }

export const TAKTY_PRESETY = [
  { dob: 2, hodnota: 4, popisek: '2/4' },
  { dob: 3, hodnota: 4, popisek: '3/4' },
  { dob: 4, hodnota: 4, popisek: '4/4' },
  { dob: 6, hodnota: 8, popisek: '6/8' },
  { dob: 12, hodnota: 8, popisek: '12/8' },
]

export const SEKCE_NAVRHY = [
  'Úvod',
  'Intro',
  'Sloka',
  'Refrén',
  'Předrefrén',
  'Mezihra',
  'Sólo',
  'Bridge',
  'Outro',
  'Konec',
]

// --- vytváření prázdných kousků ---

export function novyTakt(dob) {
  return { bunky: Array(dob).fill('') }
}

export function novyRadek(dob) {
  return { takty: [novyTakt(dob)] }
}

export function novaSekce(dob) {
  return { nazev: '', radky: [novyRadek(dob)], repetice: [] }
}

// --- efektivní takt taktu v řádku (vlastní přepis, nebo výchozí) ---

export function efektivniTakt(taktVRadku, taktVychozi) {
  return taktVRadku.takt || taktVychozi
}

// --- adresace uvnitř řádku: "flat" index buňky napříč VŠEMI takty řádku
// (takty mají různou šířku, když mají vlastní přepis, takže "index // dob"
// jako ve schématu 1 už nejde použít) ---

export function radekCelkemBunek(radek) {
  return radek.takty.reduce((sum, t) => sum + t.bunky.length, 0)
}

// {taktIdx, dobaIdx} pro daný flat index, nebo null mimo rozsah.
export function poziceVRadku(radek, flatIdx) {
  let zbyva = flatIdx
  for (let ti = 0; ti < radek.takty.length; ti++) {
    const len = radek.takty[ti].bunky.length
    if (zbyva < len) return { taktIdx: ti, dobaIdx: zbyva }
    zbyva -= len
  }
  return null
}

export function flatIndexZPozice(radek, taktIdx, dobaIdx) {
  let flat = 0
  for (let ti = 0; ti < taktIdx; ti++) flat += radek.takty[ti].bunky.length
  return flat + dobaIdx
}

// --- přidání/odebrání taktu (Tab na konci řádku / tlačítko smazat takt) ---

export function pridejTaktDoRadku(radek, dobVychozi) {
  return { ...radek, takty: [...radek.takty, novyTakt(dobVychozi)] }
}

// Smazání taktu je operace NA SEKCI (ne jen na řádku) — repetice indexují
// takty přes celou sekci, takže po smazání se musí posunout i repetice
// odkazující na takty PO tom smazaném, napříč VŠEMI řádky sekce.
//
// Smazání POSLEDNÍHO taktu řádku smaže i řádek — žádné samostatné
// "Smazat řádek" tlačítko není potřeba. Výjimka: jediný řádek sekce se
// nesmí smazat (nebylo by kam se vrátit přes Enter), místo toho se
// resetuje na jeden prázdný takt.
export function odeberTaktZeSekce(sekce, radekIdx, taktIdx, dobVychozi) {
  const globalni = globalniIndexTaktu(sekce, radekIdx, taktIdx)
  const radek = sekce.radky[radekIdx]
  const jePosledniTaktRadku = radek.takty.length === 1
  const jeJedinyRadekSekce = sekce.radky.length === 1

  let noveRadky
  if (jePosledniTaktRadku && jeJedinyRadekSekce) {
    noveRadky = [novyRadek(dobVychozi)]
  } else if (jePosledniTaktRadku) {
    noveRadky = sekce.radky.filter((_, ri) => ri !== radekIdx)
  } else {
    noveRadky = sekce.radky.map((r, ri) => {
      if (ri !== radekIdx) return r
      const takty = [...r.takty]
      takty.splice(taktIdx, 1)
      return { ...r, takty }
    })
  }

  const novaRepetice = sekce.repetice
    .filter((rep) => rep.do_taktu < globalni || rep.od_taktu > globalni)
    .map((rep) =>
      rep.od_taktu > globalni
        ? { ...rep, od_taktu: rep.od_taktu - 1, do_taktu: rep.do_taktu - 1 }
        : rep,
    )
  return { ...sekce, radky: noveRadky, repetice: novaRepetice }
}

// --- globální (v rámci sekce) index taktu — pro repetice ---

export function globalniIndexTaktu(sekce, radekIdx, taktIdx) {
  let idx = 0
  for (let r = 0; r < radekIdx; r++) idx += sekce.radky[r].takty.length
  return idx + taktIdx
}

export function pocetTaktuVSekci(sekce) {
  return sekce.radky.reduce((sum, r) => sum + r.takty.length, 0)
}

// --- délka řádku v dobách (pro info hlášku pod editorem, zrcadlí PDF) ---

export function delkaRadkuVDobach(radek, taktVychozi) {
  return radek.takty.reduce((sum, t) => sum + efektivniTakt(t, taktVychozi).dob, 0)
}

export function nejdelsiRadekVDobach(sekce, taktVychozi) {
  let max = 0
  for (const s of sekce) {
    for (const r of s.radky) {
      max = Math.max(max, delkaRadkuVDobach(r, taktVychozi))
    }
  }
  return max
}

// --- změna počtu dob taktu (globální výchozí i jednotlivý přepis sdílí
// tuhle logiku): doplnit prázdnými, nebo oříznout zprava ---

export function zpusobiZtratuZmenaTaktu(bunky, novyDob) {
  return bunky.slice(novyDob).some((b) => b !== '')
}

function zmenDobBunek(bunky, novyDob) {
  if (novyDob >= bunky.length) return [...bunky, ...Array(novyDob - bunky.length).fill('')]
  return bunky.slice(0, novyDob)
}

// Zjistí, jestli změna VÝCHOZÍHO taktu (jen na taktech BEZ vlastního
// přepisu) zahodí nějaký neprázdný obsah — dřív, než se zeptá na potvrzení.
export function zpusobiZtratuZmenaVychozihoTaktu(vsechnySekce, novyDob) {
  return vsechnySekce.some((s) =>
    s.radky.some((r) => r.takty.some((t) => !t.takt && zpusobiZtratuZmenaTaktu(t.bunky, novyDob))),
  )
}

// Aplikuje změnu výchozího taktu — jen na taktech BEZ vlastního přepisu.
// Repetice se NEZAHAZUJÍ: počet taktů se neměnil, jen počet dob v nich.
export function aplikujZmenuVychozihoTaktu(vsechnySekce, novyDob) {
  return vsechnySekce.map((s) => ({
    ...s,
    radky: s.radky.map((r) => ({
      ...r,
      takty: r.takty.map((t) => (t.takt ? t : { ...t, bunky: zmenDobBunek(t.bunky, novyDob) })),
    })),
  }))
}

// --- výběr buněk: pozice = {sekceIdx, radekIdx, bunkaIdxVRadku} ---

export function pozicePodobne(a, b) {
  return a.sekceIdx === b.sekceIdx && a.radekIdx === b.radekIdx && a.bunkaIdxVRadku === b.bunkaIdxVRadku
}

function porovnejPozice(a, b) {
  if (a.sekceIdx !== b.sekceIdx) return a.sekceIdx - b.sekceIdx
  if (a.radekIdx !== b.radekIdx) return a.radekIdx - b.radekIdx
  return a.bunkaIdxVRadku - b.bunkaIdxVRadku
}

export function vyberObsahuje(vyber, pozice) {
  return vyber.some((p) => pozicePodobne(p, pozice))
}

export function prepniVeVyberu(vyber, pozice) {
  return vyberObsahuje(vyber, pozice)
    ? vyber.filter((p) => !pozicePodobne(p, pozice))
    : [...vyber, pozice]
}

// Všechny pozice MEZI dvěma kliky "v pořadí čtení" (sekce, pak řádek, pak
// buňka) — pro Shift+klik. Může přeskočit přes víc řádků i sekcí; jestli to
// smí být repetice, se řeší až při kliku na tlačítko Repetice.
export function rozsahMeziPozicemi(zapis, a, b) {
  const [od, doPoz] = porovnejPozice(a, b) <= 0 ? [a, b] : [b, a]
  const vysledek = []
  for (let si = od.sekceIdx; si <= doPoz.sekceIdx; si++) {
    const sekce = zapis.sekce[si]
    const radekOd = si === od.sekceIdx ? od.radekIdx : 0
    const radekDo = si === doPoz.sekceIdx ? doPoz.radekIdx : sekce.radky.length - 1
    for (let ri = radekOd; ri <= radekDo; ri++) {
      const radek = sekce.radky[ri]
      const celkem = radekCelkemBunek(radek)
      const bunkaOd = si === od.sekceIdx && ri === od.radekIdx ? od.bunkaIdxVRadku : 0
      const bunkaDo = si === doPoz.sekceIdx && ri === doPoz.radekIdx ? doPoz.bunkaIdxVRadku : celkem - 1
      for (let bk = bunkaOd; bk <= bunkaDo; bk++) {
        vysledek.push({ sekceIdx: si, radekIdx: ri, bunkaIdxVRadku: bk })
      }
    }
  }
  return vysledek
}

// Unikátní seznam CELÝCH TAKTŮ (bary), které výběr zasahuje (zarovnání na
// celé takty, viz zadání) — {sekceIdx, radekIdx, taktIdx}.
export function taktyVeVyberu(zapis, vyber) {
  const klice = new Set()
  const vysledek = []
  for (const pozice of vyber) {
    const radek = zapis.sekce[pozice.sekceIdx].radky[pozice.radekIdx]
    const p = poziceVRadku(radek, pozice.bunkaIdxVRadku)
    if (!p) continue
    const klic = `${pozice.sekceIdx}:${pozice.radekIdx}:${p.taktIdx}`
    if (!klice.has(klic)) {
      klice.add(klic)
      vysledek.push({ sekceIdx: pozice.sekceIdx, radekIdx: pozice.radekIdx, taktIdx: p.taktIdx })
    }
  }
  return vysledek
}

// --- kontrola výběru + založení repetice (jen v rámci JEDNÉ sekce) ---

export function zkontrolujVyberProRepetici(zapis, vyber) {
  if (vyber.length === 0) {
    return { ok: false, hlaska: 'Nejdřív vyber aspoň jeden takt.' }
  }
  const sekceIdxy = new Set(vyber.map((p) => p.sekceIdx))
  if (sekceIdxy.size > 1) {
    return { ok: false, hlaska: 'Repetice jen v rámci jedné sekce.' }
  }
  const sekceIdx = [...sekceIdxy][0]
  const sekce = zapis.sekce[sekceIdx]
  const takty = taktyVeVyberu(zapis, vyber)
  const globalniIndexy = takty.map((t) => globalniIndexTaktu(sekce, t.radekIdx, t.taktIdx))
  const od_taktu = Math.min(...globalniIndexy)
  const do_taktu = Math.max(...globalniIndexy)
  const prekryv = sekce.repetice.some((r) => od_taktu <= r.do_taktu && do_taktu >= r.od_taktu)
  if (prekryv) {
    return { ok: false, hlaska: 'Tenhle úsek se překrývá s existující repeticí.' }
  }
  return { ok: true, sekceIdx, od_taktu, do_taktu }
}

// --- kontrola + aplikace tlačítka "Změnit takt" (bez omezení na 1 sekci —
// jde jen o přepsání/zrušení taktu vybraných barů, počet barů se neměnní,
// takže repetice zůstávají v pořádku beze změny) ---

export function zpusobiZtratuZmenaVyberu(zapis, vyber, novyDob) {
  return taktyVeVyberu(zapis, vyber).some(({ sekceIdx, radekIdx, taktIdx }) => {
    const t = zapis.sekce[sekceIdx].radky[radekIdx].takty[taktIdx]
    return zpusobiZtratuZmenaTaktu(t.bunky, novyDob)
  })
}

// `novyTakt` je {dob, hodnota}, nebo null pro "výchozí" (zruší přepis).
export function aplikujZmenuTaktuNaVyber(zapis, vyber, novyTakt) {
  const cile = new Set(
    taktyVeVyberu(zapis, vyber).map((c) => `${c.sekceIdx}:${c.radekIdx}:${c.taktIdx}`),
  )
  return {
    ...zapis,
    sekce: zapis.sekce.map((s, si) => ({
      ...s,
      radky: s.radky.map((r, ri) => ({
        ...r,
        takty: r.takty.map((t, ti) => {
          if (!cile.has(`${si}:${ri}:${ti}`)) return t
          const dob = novyTakt ? novyTakt.dob : zapis.takt.dob
          const bunky = zmenDobBunek(t.bunky, dob)
          return novyTakt ? { bunky, takt: novyTakt } : { bunky }
        }),
      })),
    })),
  }
}
