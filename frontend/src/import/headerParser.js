// Hlavička stránky písně: "NÁZEV – Interpret   KÓD". Oddělovač je v
// referenčním dokumentu ŠUBAPS vždy en dash (U+2013), ale parser snese i em
// dash, horizontální čárku a normální spojovník — jen musí mít mezeru z obou
// stran (jinak by to byla pomlčka uvnitř slova/názvu, ne oddělovač). Kód je
// trojmístné číslo na úplném konci řádku; může chybět (viz strana 64 v
// referenčním dokumentu), interpret může chybět taky (2 písně).
//
// Nestrukturované zpěvníky (v2, viz 80s_zpevnik.pdf) navíc nemívají ŽÁDNÝ
// oddělovač ("Atlantis Is Calling") ani kód — tam headerFound rozhoduje
// signál z fontu (viz headerFont.js), ne text sám. `fontOdlisny=true`
// znamená "tenhle řádek je nahoře na stránce stylově jiný než zbytek" a
// stačí to k uznání za hlavičku i bez pomlčky/kódu.
const DASH_CHARS = '\\-\u2010\u2011\u2012\u2013\u2014\u2015'
const DASH_SPLIT_RE = new RegExp(`\\s[${DASH_CHARS}]\\s`, 'g')
const KOD_AT_END_RE = /(\d{3})\s*$/

// Balast v hlavičce nestrukturovaných zpěvníků — odstranit PŘED rozdělením
// na název/interpret, ne až po něm (jinak by "Lyrics" skončilo jako součást
// interpreta u "Rod Stewart – Baby Jane Lyrics").
const ARTIST_BAND_RE = /\s*Artist\s*\(\s*Band\s*\)\s*:\s*/i
const BAND_SUFFIX_RE = /\s*\(\s*Band\s*\)\s*/gi
const LYRICS_SUFFIX_RE = /\s+Lyrics\s*$/i
const PAGE_SUFFIX_RE = /\s+Page\s+\d+\s*$/i
// Uvozovky kolem CELÉHO řádku ("Joyride" -> Joyride) — kotvené na začátek/konec,
// ať se nedotknou apostrofu uprostřed slova (Rockin').
const WRAPPED_QUOTES_RE = /^["“„'‘](.+)["”‘’']$/

export function ocistiHlavicku(rawLine) {
  let s = (rawLine || '').trim()
  if (!s) return s
  // "Artist(Band):" je v tomhle souboru oddělovač název/interpret, i když
  // nemá mezery kolem — převede se na standardní " – ", ať ho pak rozdělí
  // stejná logika jako běžnou pomlčku.
  s = s.replace(ARTIST_BAND_RE, ' – ')
  s = s.replace(BAND_SUFFIX_RE, ' ')
  s = s.replace(LYRICS_SUFFIX_RE, '')
  s = s.replace(PAGE_SUFFIX_RE, '')
  s = s.replace(/\s+/g, ' ').trim()
  const uvozovky = s.match(WRAPPED_QUOTES_RE)
  if (uvozovky) s = uvozovky[1].trim()
  return s
}

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
// (viz strana 64). `fontOdlisny` navíc uzná za hlavičku i řádek BEZ pomlčky
// a BEZ kódu ("Atlantis Is Calling") — parser pak nemá co rozdělit, takže
// celý (očištěný) řádek jde jako název a interpret zůstává prázdný; pořadí
// název/interpret u řádků S pomlčkou parser NEURČUJE (viz zadání), nechává
// první část jako název — na uživateli je to prohodit tlačítkem v tabulce.
export function parseHeaderLine(rawLine, fontOdlisny = false) {
  const prazdny = { headerFound: false, kod: null, nazev: '', interpret: '' }
  const line = ocistiHlavicku(rawLine)
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

  const headerFound = kod !== null || Boolean(split) || fontOdlisny
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
