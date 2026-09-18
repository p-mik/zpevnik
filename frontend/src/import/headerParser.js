// Hlavička stránky písně: "NÁZEV – Interpret   KÓD". Oddělovač je v
// referenčním dokumentu vždy en dash (U+2013), ale parser snese i em dash,
// horizontální čárku a normální spojovník — jen musí mít mezeru z obou stran
// (jinak by to byla pomlčka uvnitř slova/názvu, ne oddělovač). Kód je
// trojmístné číslo na úplném konci řádku; může chybět (viz strana 64 v
// referenčním dokumentu), interpret může chybět taky (2 písně).
const DASH_CHARS = '\\-\u2010\u2011\u2012\u2013\u2014\u2015'
const DASH_SPLIT_RE = new RegExp(`\\s[${DASH_CHARS}]\\s`, 'g')
const KOD_AT_END_RE = /(\d{3})\s*$/

function splitOnLastDash(text) {
  let last = null
  let m
  DASH_SPLIT_RE.lastIndex = 0
  while ((m = DASH_SPLIT_RE.exec(text))) last = m
  if (!last) return null
  return {
    before: text.slice(0, last.index).trim(),
    after: text.slice(last.index + last[0].length).trim(),
  }
}

// Vrací { headerFound, kod, nazev, interpret }. `headerFound` je true, jakmile
// se rozpozná ALESPOŇ kód, NEBO vzor "název – interpret" — i bez kódu se to
// pak v tabulce ukáže jako rozpoznaná píseň, jen s chybějícím kódem
// (viz strana 64), místo aby to spadlo do "stránka bez hlavičky".
export function parseHeaderLine(rawLine) {
  const prazdny = { headerFound: false, kod: null, nazev: '', interpret: '' }
  const line = (rawLine || '').trim()
  if (!line) return prazdny

  let remainder = line
  let kod = null
  const kodMatch = remainder.match(KOD_AT_END_RE)
  if (kodMatch) {
    kod = parseInt(kodMatch[1], 10)
    remainder = remainder.slice(0, kodMatch.index).trim()
  }

  const split = splitOnLastDash(remainder)
  const nazev = split ? split.before : remainder
  const interpret = split ? split.after : ''

  const headerFound = kod !== null || Boolean(split)
  if (!headerFound) return prazdny

  return { headerFound: true, kod, nazev, interpret }
}

// Uppercase -> běžné psaní, jen jako NÁVRH (viz zadání — u zkratek by to
// natvrdo nadělalo paseku). Neřeší diakritiku/výjimky, jen první písmeno
// každého slova velké, zbytek malý.
export function navrhniBezneJmeno(nazevVerzalkami) {
  return nazevVerzalkami
    .toLowerCase()
    .replace(/(^|[\s([{'"„])\p{L}/gu, (znak) => znak.toUpperCase())
}
