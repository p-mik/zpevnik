// Čistá logika akordového zápisu (viz PC_zpevnik_akordovy_zapis.md) — žádné
// React, žádné API, jen transformace nad daty. Zrcadlí schéma, které ověřuje
// server (AkordovyZapisSerializer): `bunky.length` je vždy násobek `dob`,
// `repetice` jsou indexy taktů V RÁMCI ŘÁDKU (0-based, `do_takt` včetně).

export const PRAZDNY_ZAPIS = { schema: 1, takt: { dob: 4, hodnota: 4 }, tempo: null, radky: [] }

export const TAKTY_PRESETY = [
  { dob: 2, hodnota: 4, popisek: '2/4' },
  { dob: 3, hodnota: 4, popisek: '3/4' },
  { dob: 4, hodnota: 4, popisek: '4/4' },
  { dob: 6, hodnota: 8, popisek: '6/8' },
  { dob: 12, hodnota: 8, popisek: '12/8' },
]

// Datalist pro pole sekce — volný text je pořád možný (<input list>, ne <select>).
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

export function novyRadek(dob) {
  return { sekce: '', bunky: Array(dob).fill(''), repetice: [] }
}

export function pocetTaktu(radek, dob) {
  return radek.bunky.length / dob
}

// Přidá jeden prázdný takt na konec řádku — používá Tab na poslední buňce
// (viz zadání: "Tab na konci řádku přidá nový takt a skočí do něj").
export function pridejTakt(radek, dob) {
  return { ...radek, bunky: [...radek.bunky, ...Array(dob).fill('')] }
}

// Smaže takt na daném indexu. Repetice, které se s ním PŘEKRÝVAJÍ, se
// zahodí (nedá se rozumně dopočítat, kam by měly po smazání sahat) —
// repetice ležící celé PŘED smazaným taktem zůstávají beze změny, celé PO
// něm se posunou o jeden index dolů.
export function odeberTakt(radek, indexTaktu, dob) {
  const noveBunky = [...radek.bunky]
  noveBunky.splice(indexTaktu * dob, dob)
  const novaRepetice = radek.repetice
    .filter((r) => r.do_takt < indexTaktu || r.od_takt > indexTaktu)
    .map((r) =>
      r.od_takt > indexTaktu
        ? { ...r, od_takt: r.od_takt - 1, do_takt: r.do_takt - 1 }
        : r,
    )
  return { ...radek, bunky: noveBunky, repetice: novaRepetice }
}

// Změna taktu (dob) nad NEPRÁZDNÝM zápisem: buňky zůstávají (jen se
// přeskládají na nové hranice taktů, viz zadání), doplní se prázdnými na
// násobek nového dob. Existující repetice odkazovaly na hranice PODLE
// STARÉHO taktu — po přeskládání by ukazovaly jinam, než uživatel čekal,
// takže se (vědomě nad rámec doslovného zadání, ale bezpečněji než tichá
// chyba) zahazují; volající o tom musí uživatele v potvrzovacím dialogu
// informovat.
export function preskladejNaNovyTakt(radky, novyDob) {
  return radky.map((radek) => {
    const zbytek = radek.bunky.length % novyDob
    const doplneni = zbytek === 0 ? 0 : novyDob - zbytek
    return {
      ...radek,
      bunky: doplneni > 0 ? [...radek.bunky, ...Array(doplneni).fill('')] : radek.bunky,
      repetice: [],
    }
  })
}

function poziceKlic(p) {
  return `${p.radek}:${p.bunka}`
}

export function pozicePodobne(a, b) {
  return a.radek === b.radek && a.bunka === b.bunka
}

function porovnejPozice(a, b) {
  if (a.radek !== b.radek) return a.radek - b.radek
  return a.bunka - b.bunka
}

// Všechny pozice MEZI dvěma kliky "v pořadí čtení" (řádek, pak buňka) —
// pro Shift+klik. Může přeskočit přes víc řádků; jestli to smí být repetice,
// se řeší až při kliku na tlačítko Repetice (viz zkontrolujVyberProRepetici).
export function rozsahMeziPozicemi(radky, a, b) {
  const [od, doPozice] = porovnejPozice(a, b) <= 0 ? [a, b] : [b, a]
  const vysledek = []
  for (let r = od.radek; r <= doPozice.radek; r++) {
    const pocetBunek = radky[r].bunky.length
    const start = r === od.radek ? od.bunka : 0
    const konec = r === doPozice.radek ? doPozice.bunka : pocetBunek - 1
    for (let bk = start; bk <= konec; bk++) vysledek.push({ radek: r, bunka: bk })
  }
  return vysledek
}

export function vyberObsahuje(vyber, pozice) {
  return vyber.some((p) => pozicePodobne(p, pozice))
}

export function prepniVeVyberu(vyber, pozice) {
  return vyberObsahuje(vyber, pozice)
    ? vyber.filter((p) => !pozicePodobne(p, pozice))
    : [...vyber, pozice]
}

// Zarovná výběr (buňky) na CELÉ TAKTY dané řádky (viz zadání: "výběr se
// zarovná na celé takty") a vrátí (od_takt, do_takt), nebo null pro
// prázdný výběr.
export function zarovnejNaTakty(vyberVRadku, dob) {
  if (vyberVRadku.length === 0) return null
  const indexy = vyberVRadku.map((p) => Math.floor(p.bunka / dob))
  return { od_takt: Math.min(...indexy), do_takt: Math.max(...indexy) }
}

// Zkontroluje výběr před založením repetice — vrací buď {ok:true, od_takt,
// do_takt}, nebo {ok:false, hlaska}. Nekontroluje nic přes API, jen to, co
// jde ověřit lokálně (řádek, překryv) — server je poslední instance.
export function zkontrolujVyberProRepetici(vyber, radky, dob) {
  if (vyber.length === 0) {
    return { ok: false, hlaska: 'Nejdřív vyber aspoň jeden takt.' }
  }
  const radkyVeVyberu = new Set(vyber.map((p) => p.radek))
  if (radkyVeVyberu.size > 1) {
    return { ok: false, hlaska: 'Repetice jen v rámci jednoho řádku.' }
  }
  const indexRadku = [...radkyVeVyberu][0]
  const { od_takt, do_takt } = zarovnejNaTakty(vyber, dob)
  const radek = radky[indexRadku]
  const prekryv = radek.repetice.some(
    (r) => od_takt <= r.do_takt && do_takt >= r.od_takt,
  )
  if (prekryv) {
    return { ok: false, hlaska: 'Tenhle úsek se překrývá s existující repeticí.' }
  }
  return { ok: true, indexRadku, od_takt, do_takt }
}
