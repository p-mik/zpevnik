// Detekce hlavičky podle fontu (v2 importu). PDF.js z veřejného API
// nevrací skutečný název fontu (item.fontName je jen interní alias jako
// "g_d0_f2" a textContent.styles[...].fontFamily je obecné "sans-serif" bez
// ohledu na to, jestli je font Tahoma-Bold nebo Times) — "je to Bold" proto
// nejde zjistit přímo. Ověřeno na referenčním 80s_zpevnik.pdf.
//
// Funguje ale spolehlivěji dostupný nepřímý signál: hlavička je vysázená
// JINÝM fontem než většina obsahu stránky. Jako "většinový" font se bere ten
// s nejvíc znaky CELKEM na stránce (ne nejvíc řádky) — u zpěvníku s akordy
// (ŠUBAPS) mívá hlavička STEJNÝ font jako akordové řádky (obojí "tučné"),
// takže by ho počítání podle řádků mohlo mylně označit za většinový; počítání
// podle znaků ho spolehlivě přehlasují dlouhé řádky textu písně.
//
// První řádek stránky se bere jako celek (i mimo levou polovinu — u ŠUBAPS
// je hlavička zarovnaná doprava/na střed, takže "jen levá polovina" by ji
// useknutím za polovinou zkomolila). Levá polovina se použije JEN když první
// řádek evidentně slepil dva sloupce — na to NESTAČÍ, že kousky leží na obou
// stranách středu (dlouhý jednosloupcový titulek s kódem na konci přes
// střed běžně přesahuje taky, viz "PĚKNÁ, PĚKNÁ, PĚKNÁ – J. Ledecký 103" v
// ŠUBAPS), musí se navíc lišit FONT mezi levou a pravou částí — to nastává
// jen u genuinního sloupcového slepení, kde pravá půlka patří jinému textu
// (viz strany 18/35/37/43 v 80s_zpevnik.pdf, titulek jedním fontem + slepený
// začátek pravého sloupce fontem těla).
export function najdiKandidataHlavicky(items, pageWidth, radky) {
  if (!radky.length) return { text: '', fontOdlisny: false }

  let prvni = radky[0]
  const mid = pageWidth / 2
  const vlevoItems = prvni.items.filter((i) => i.transform[4] < mid)
  const vpravoItems = prvni.items.filter((i) => i.transform[4] >= mid)
  const fontyVlevo = new Set(vlevoItems.map((i) => i.fontName))
  const slepeny =
    vlevoItems.length > 0 &&
    vpravoItems.length > 0 &&
    vpravoItems.some((i) => !fontyVlevo.has(i.fontName))
  if (slepeny) {
    prvni = {
      ...prvni,
      items: vlevoItems,
      text: vlevoItems
        .map((i) => i.str)
        .join('')
        .replace(/\s+/g, ' ')
        .trim(),
    }
  }
  if (!prvni.text) return { text: '', fontOdlisny: false }

  const znakuPodleFontu = new Map()
  for (const it of items) {
    if (!it.str) continue
    znakuPodleFontu.set(it.fontName, (znakuPodleFontu.get(it.fontName) || 0) + it.str.length)
  }
  let vetsinovyFont = null
  let nejvic = -1
  for (const [font, znaku] of znakuPodleFontu) {
    if (znaku > nejvic) {
      nejvic = znaku
      vetsinovyFont = font
    }
  }

  const fontOdlisny = prvni.items.some((i) => i.fontName !== vetsinovyFont)
  return { text: prvni.text, fontOdlisny }
}
