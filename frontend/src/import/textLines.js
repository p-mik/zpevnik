// Rekonstrukce "řádků" z PDF.js textContent položek — ty samy o sobě nemají
// pojem řádku, jen jednotlivé kusy textu s pozicí (transform matice). Seskupí
// se podle Y (s tolerancí), uvnitř řádku se seřadí podle X, řádky pak shora
// dolů podle Y (PDF má osu Y rostoucí vzhůru, takže sestupně).
const Y_TOLERANCE = 2

export async function extractPageLines(pdfDoc, pageNumber) {
  const page = await pdfDoc.getPage(pageNumber)
  const textContent = await page.getTextContent()
  return groupItemsIntoLines(textContent.items)
}

export function groupItemsIntoLines(items) {
  const clusters = [] // { y, items: [] }

  for (const item of items) {
    // Pozor: filtruje se jen opravdu prázdný string, NE "je to jen mezera".
    // Mezery často přijdou jako VLASTNÍ položky (samostatný text run) — bez
    // nich by se sousední slova slila k sobě bez mezery při skládání řádku.
    if (!item.str) continue
    const y = item.transform[5]
    let cluster = clusters.find((c) => Math.abs(c.y - y) <= Y_TOLERANCE)
    if (!cluster) {
      cluster = { y, items: [] }
      clusters.push(cluster)
    }
    cluster.items.push(item)
  }

  return clusters
    .sort((a, b) => b.y - a.y)
    .map((c) => ({
      y: c.y,
      text: c.items
        .slice()
        .sort((a, b) => a.transform[4] - b.transform[4])
        .map((i) => i.str)
        .join('')
        .replace(/\s+/g, ' ')
        .trim(),
      items: c.items,
    }))
    .filter((line) => line.text)
}

// Nejmenší úsek na levé/pravé polovině stránky — použito pro odvození
// názvů kategorií z obsahu (viz deriveKategorie.js), kde je dvousloupcová
// tabulka a textContent samotný sloupce nerozlišuje.
export function splitItemsByColumn(items, pageWidthMidpoint) {
  const left = []
  const right = []
  for (const item of items) {
    if (!item.str) continue
    const x = item.transform[4]
    if (x < pageWidthMidpoint) left.push(item)
    else right.push(item)
  }
  return { left, right }
}
