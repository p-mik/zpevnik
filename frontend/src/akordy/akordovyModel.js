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

// Sekce jen s nadpisem, bez řádků (viz schéma — "Sloka 2 = Sloka 1" apod.,
// obsah přijde přes repetici nebo se odkazuje jinak, nepotřebuje vlastní
// takty). Jednu z variant "+ Přidat sekci" v AkordovyMrizka.
export function novaSekceBezRadku() {
  return { nazev: '', radky: [], repetice: [] }
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
// "Smazat řádek" tlačítko není potřeba. Smazání posledního taktu
// JEDINÉHO řádku sekce nechá sekci BEZ řádků (`radky: []`, viz schéma
// — sekce jen s nadpisem) místo dřívějšího resetu na 1 prázdný takt;
// zpátky na obsah se jde přes "+ Přidat řádek" (viz AkordovyMrizka).
export function odeberTaktZeSekce(sekce, radekIdx, taktIdx) {
  const globalni = globalniIndexTaktu(sekce, radekIdx, taktIdx)
  const radek = sekce.radky[radekIdx]
  const jePosledniTaktRadku = radek.takty.length === 1
  const jeJedinyRadekSekce = sekce.radky.length === 1

  let noveRadky
  if (jePosledniTaktRadku && jeJedinyRadekSekce) {
    noveRadky = []
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

// --- přesun sekcí (PC_zpevnik_akordy_ovladani.md bod 2) ---

// Posune sekci na indexu `sekceIdx` o jednu pozici (`smer` -1 nahoru,
// +1 dolů) — prosté prohození dvou položek pole. Repetice (a volty)
// se NEPŘEPOČÍTÁVAJÍ: indexují takty v RÁMCI SEKCE, ne napříč sekcemi
// (viz modul docstring), takže přesun celé sekce s sebou nic netahá.
// Mimo rozsah (první sekce nahoru, poslední dolů) vrátí pole beze
// změny — volající (AkordovyMrizka) tlačítko pro tenhle směr ani
// nezobrazí, tohle je jen pojistka.
export function posunSekciVPoli(vsechnySekce, sekceIdx, smer) {
  const cil = sekceIdx + smer
  if (cil < 0 || cil >= vsechnySekce.length) return vsechnySekce
  const nove = [...vsechnySekce]
  ;[nove[sekceIdx], nove[cil]] = [nove[cil], nove[sekceIdx]]
  return nove
}

// --- rozdělení / spojení sekcí (viz zadání bod 3) ---

// Rozdělí sekci na dvě OD `radekIdx` (musí být >0 — první řádek sekce se
// dělit nedá, tam by vznikla prázdná horní část). Horní si nechá řádky
// [0..radekIdx-1] a repetice, které leží CELÉ v ní; dolní dostane řádky
// [radekIdx..] a repetice, které leží CELÉ v ní, s indexy posunutými o
// počet taktů horní části (repetice indexují takty relativně k VLASTNÍ
// sekci, viz modul docstring). Repetice PŘES hranici dělení (začíná
// nahoře, končí dole) rozdělení jako celek odmítne — vrátí `{ok:false}`
// místo aby ji tiše osekala nebo přesunula.
export function rozdelSekciOdRadku(sekce, radekIdx) {
  const hraniceTaktu = sekce.radky
    .slice(0, radekIdx)
    .reduce((sum, r) => sum + r.takty.length, 0)

  const pretina = sekce.repetice.some(
    (r) => r.od_taktu < hraniceTaktu && r.do_taktu >= hraniceTaktu,
  )
  if (pretina) {
    return { ok: false, hlaska: 'Tady je repetice přes více řádků, nejdřív ji zruš.' }
  }

  const horniRepetice = sekce.repetice.filter((r) => r.do_taktu < hraniceTaktu)
  const dolniRepetice = sekce.repetice
    .filter((r) => r.od_taktu >= hraniceTaktu)
    .map((r) => ({
      ...r,
      od_taktu: r.od_taktu - hraniceTaktu,
      do_taktu: r.do_taktu - hraniceTaktu,
    }))

  const puvodni = { ...sekce, radky: sekce.radky.slice(0, radekIdx), repetice: horniRepetice }
  const nova = { nazev: '', radky: sekce.radky.slice(radekIdx), repetice: dolniRepetice }
  return { ok: true, puvodni, nova }
}

// Spojí `aktualni` sekci S PŘEDCHOZÍ (`predchozi`) do jedné — opak
// `rozdelSekciOdRadku`. Název: vyhrává `predchozi` (název `aktualni` se
// zahodí, viz zadání). Repetice `aktualni` se přeindexují o počet taktů
// `predchozi` (v součtu jsou teď až ZA nimi), repetice `predchozi`
// zůstávají beze změny (jsou pořád na začátku).
export function spojSeSPredchozi(predchozi, aktualni) {
  const posun = pocetTaktuVSekci(predchozi)
  const posunutaRepetice = aktualni.repetice.map((r) => ({
    ...r,
    od_taktu: r.od_taktu + posun,
    do_taktu: r.do_taktu + posun,
  }))
  return {
    nazev: predchozi.nazev,
    radky: [...predchozi.radky, ...aktualni.radky],
    repetice: [...predchozi.repetice, ...posunutaRepetice],
  }
}

// --- rozdělení řádku na Enter uprostřed (viz zadání) ---

// Rozdělí řádek `radekIdx` v sekci NA DVA od taktu `taktIdx` (musí být
// >0 a < počet taktů řádku — na hranici MEZI takty, ne na začátku ani na
// konci, tam by split nedělal nic užitečného). Takty [taktIdx..] se
// přesunou do NOVÉHO řádku vloženého hned za `radekIdx`, UVNITŘ STEJNÉ
// sekce — pořadí (a tedy globální indexy, viz `globalniIndexTaktu`)
// taktů v sekci se tím vůbec nemění, jen se mezi ně vloží zalomení
// řádku, takže na rozdíl od `rozdelSekciOdRadku` repetice nepotřebují
// přepočet indexů. Přesto: repetice přes hranici zalomení (začíná před
// `taktIdx`, končí na něm nebo za ním) rozdělení odmítne stejnou
// hláškou jako `rozdelSekciOdRadku` — i když by šla geometricky
// zobrazit (repetice smí přes víc řádků JEDNÉ sekce), řádkový split ji
// úmyslně nepodporuje (zadání to výslovně chce takhle).
export function rozdelRadekOdTaktu(sekce, radekIdx, taktIdx) {
  const radek = sekce.radky[radekIdx]
  const hraniceTaktu = globalniIndexTaktu(sekce, radekIdx, taktIdx)

  const pretina = sekce.repetice.some(
    (r) => r.od_taktu < hraniceTaktu && r.do_taktu >= hraniceTaktu,
  )
  if (pretina) {
    return { ok: false, hlaska: 'Tady je repetice přes více řádků, nejdřív ji zruš.' }
  }

  const noveRadky = [...sekce.radky]
  noveRadky.splice(
    radekIdx,
    1,
    { ...radek, takty: radek.takty.slice(0, taktIdx) },
    { takty: radek.takty.slice(taktIdx) },
  )
  return { ok: true, sekce: { ...sekce, radky: noveRadky } }
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
