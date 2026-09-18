import { groupItemsIntoLines } from './textLines'
import { parseHeaderLine } from './headerParser'
import { najdiKandidataHlavicky } from './headerFont'

// Projde všechny stránky, vrátí návrh (uživatel ho potvrzuje/opravuje v
// kontrolní tabulce — nikdy se rovnou nezakládá). Výchozí akce podle zadání:
//   - prakticky prázdná stránka (přebal, prázdná strana) -> vyřadit
//   - hlavička rozpoznaná (text NEBO font)                -> nová píseň
//   - strana 1 bez hlavičky                               -> vyřadit (obsah)
//   - jiná strana bez hlavičky                             -> pokračování předchozí
export async function parseAllPages(pdfDoc, onProgress) {
  const numPages = pdfDoc.numPages
  const pages = []

  for (let n = 1; n <= numPages; n++) {
    const page = await pdfDoc.getPage(n)
    const viewport = page.getViewport({ scale: 1 })
    const textContent = await page.getTextContent()
    const radky = groupItemsIntoLines(textContent.items)

    const celkovaDelkaTextu = radky.reduce((sum, r) => sum + r.text.length, 0)
    const { text: kandidatText, fontOdlisny } = najdiKandidataHlavicky(
      textContent.items,
      viewport.width,
      radky,
    )
    // Strana 1 bývá obsah/přebal (viz akce níž) — nadpis kategorie v obsahu
    // (typicky taky tučný/jiný font) by font signálem prošel jako "hlavička"
    // a přebil by tenhle výchozí předpoklad. Tady se proto věří jen
    // spolehlivějšímu textovému vzoru (pomlčka/kód), stejně jako předtím.
    const parsed = parseHeaderLine(kandidatText, n === 1 ? false : fontOdlisny)

    let action
    if (celkovaDelkaTextu < 3) {
      action = 'discard'
    } else if (parsed.headerFound) {
      action = 'new'
    } else if (n === 1) {
      action = 'discard'
    } else {
      action = 'continuation'
    }

    pages.push({
      page: n,
      text: kandidatText,
      headerFound: parsed.headerFound,
      kod: parsed.kod,
      nazev: parsed.nazev,
      interpret: parsed.interpret,
      action,
      // Zmrzlý PRVOTNÍ odhad parseru — na rozdíl od `action` (co se pak ještě
      // mění v tabulce) se tohle po zbytek importu nemění. Řádek, kde `action`
      // pořád sedí s tímhle odhadem, je "pokračování z odhadu" (viz zadání
      // bod 6, "zvýraznit, že jde o odhad") — jakmile ho uživatel přepne na
      // něco jiného, badge se ztratí, i kdyby se pak vrátil zpátky.
      parsovanaAkce: action,
    })

    onProgress?.(n, numPages)
  }

  return pages
}
