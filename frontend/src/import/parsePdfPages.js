import { extractPageLines } from './textLines'
import { parseHeaderLine } from './headerParser'

// Projde všechny stránky, vrátí návrh (uživatel ho potvrzuje/opravuje v
// kontrolní tabulce — nikdy se rovnou nezakládá). Výchozí akce podle zadání:
//   - prakticky prázdná stránka (přebal, prázdná strana) -> vyřadit
//   - hlavička rozpoznaná                                -> nová píseň
//   - strana 1 bez hlavičky                               -> vyřadit (obsah)
//   - jiná strana bez hlavičky                             -> pokračování předchozí
export async function parseAllPages(pdfDoc, onProgress) {
  const numPages = pdfDoc.numPages
  const pages = []

  for (let n = 1; n <= numPages; n++) {
    const lines = await extractPageLines(pdfDoc, n)
    const firstLine = lines[0]?.text || ''
    const celkovaDelkaTextu = lines.reduce((sum, l) => sum + l.text.length, 0)
    const parsed = parseHeaderLine(firstLine)

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
      text: firstLine,
      headerFound: parsed.headerFound,
      kod: parsed.kod,
      nazev: parsed.nazev,
      interpret: parsed.interpret,
      action,
    })

    onProgress?.(n, numPages)
  }

  return pages
}
