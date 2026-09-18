import { groupItemsIntoLines, splitItemsByColumn } from './textLines'

// Bez \b schválně: v obsahu bývá kód slepený rovnou s názvem bez mezery
// ("101You're beautiful"), takže mezi číslicí a další literou často není
// slovní hranice vůbec (a u titulů začínajících diakritikou, jako "Šrouby",
// se JS \b navíc chová nekonzistentně — "š" mimo /u mód není \w). Samotné
// tři číslice na začátku řádku stačí, kategorie samy o sobě čísly nezačínají.
const KOD_LEADING_RE = /^(\d)\d{2}/

// Skupiny podle první číslice kódu se odvozují z rozpoznaných písní — to
// funguje vždycky, bez ohledu na formát obsahu. Jména kategorií se navíc
// zkusí vytáhnout z obsahové stránky (dvousloupcová tabulka: název kategorie
// jako řádek bez čísla, hned nad prvním číslovaným řádkem svého sloupce).
// Když se nic nenajde, spadne se na obecný název — uživatel ho stejně musí
// umět přejmenovat nebo celou kategorii odmítnout (viz zadání).
export async function navrhniNazvyKategorii(pdfDoc, obsahPageNumber = 1) {
  try {
    const page = await pdfDoc.getPage(obsahPageNumber)
    const viewport = page.getViewport({ scale: 1 })
    const textContent = await page.getTextContent()
    const { left, right } = splitItemsByColumn(textContent.items, viewport.width / 2)

    const labels = new Map()
    for (const [digit, nazev] of extractColumnLabels(left)) labels.set(digit, nazev)
    for (const [digit, nazev] of extractColumnLabels(right)) labels.set(digit, nazev)
    return labels
  } catch {
    // Obsahová stránka v jiném formátu, než se čekalo — ať appka nespadne,
    // jen se nabídnou obecné názvy kategorií.
    return new Map()
  }
}

function extractColumnLabels(items) {
  const lines = groupItemsIntoLines(items)
  const labels = new Map()
  let pendingLabel = null

  for (const line of lines) {
    const kodMatch = line.text.match(KOD_LEADING_RE)
    if (kodMatch) {
      const digit = kodMatch[1]
      if (pendingLabel && !labels.has(digit)) labels.set(digit, pendingLabel)
      pendingLabel = null
    } else {
      pendingLabel = titleCaseLabel(line.text)
    }
  }
  return labels
}

function titleCaseLabel(text) {
  return text.toLowerCase().replace(/(^|\s)\p{L}/gu, (znak) => znak.toUpperCase())
}

export function buildKategorieState(songs, labels) {
  const digits = new Set()
  for (const s of songs) {
    if (s.kod != null) digits.add(String(s.kod)[0])
  }
  return [...digits]
    .sort()
    .map((digit) => ({
      digit,
      nazev: labels.get(digit) || `Kategorie ${digit}xx`,
      vytvorit: true,
      pocet: songs.filter((s) => s.kod != null && String(s.kod)[0] === digit).length,
    }))
}
