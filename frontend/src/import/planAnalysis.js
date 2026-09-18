// Přemění plochý seznam stránek (jedna položka = jedna stránka PDF, viz
// useImportPlan.js) na seznam písní. 'discard' stránky se přeskočí, ale
// NEPŘERUŠÍ běžící 'continuation' řetězec — obsah/prázdná strana uprostřed
// vyřazená z importu neroztrhne dvoustránkovou píseň kolem sebe.
export function groupPagesIntoSongs(pages) {
  const songs = []
  const orphanConstinuations = []
  let current = null

  for (const p of pages) {
    if (p.action === 'discard') continue
    if (p.action === 'new') {
      current = {
        kod: p.kod,
        nazev: p.nazev,
        interpret: p.interpret,
        stranky: [p.page],
        definujiciStrana: p.page,
      }
      songs.push(current)
    } else if (p.action === 'continuation') {
      if (current) {
        current.stranky.push(p.page)
      } else {
        orphanConstinuations.push(p.page)
      }
    }
  }

  return { songs, orphanConstinuations }
}

// Problémy klíčované číslem stránky (jedna stránka může nést víc problémů) —
// tabulka je page-indexovaná, takže se takhle dají nejsnáz vykreslit jako
// odznaky u řádku. `existingKody` je Set kódů, co už jsou v databázi.
export function analyzeProblems(pages, songs, orphanConstinuations, existingKody) {
  const problems = new Map() // page -> [{type, message}]

  function pridej(page, type, message) {
    if (!problems.has(page)) problems.set(page, [])
    problems.get(page).push({ type, message })
  }

  for (const page of orphanConstinuations) {
    pridej(page, 'orphan-continuation', 'Pokračování bez předchozí písně v importu')
  }

  for (const p of pages) {
    if (p.action !== 'discard' && !p.headerFound) {
      pridej(p.page, 'bez-hlavicky', 'Na stránce se nenašla hlavička')
    }
  }

  const kodCounts = new Map()
  for (const s of songs) {
    if (s.kod == null) continue
    kodCounts.set(s.kod, (kodCounts.get(s.kod) || 0) + 1)
  }

  for (const s of songs) {
    if (s.kod == null) {
      pridej(s.definujiciStrana, 'chybi-kod', 'Chybí kód')
    } else if (kodCounts.get(s.kod) > 1) {
      pridej(s.definujiciStrana, 'duplicitni-kod-import', `Kód ${s.kod} se v importu opakuje`)
    } else if (existingKody && existingKody.has(s.kod)) {
      pridej(s.definujiciStrana, 'duplicitni-kod-db', `Kód ${s.kod} už je v databázi`)
    }
    if (!s.interpret) {
      pridej(s.definujiciStrana, 'chybi-interpret', 'Chybí interpret')
    }
  }

  return problems
}

export function planJeValidni(songs, orphanConstinuations, problems) {
  if (songs.length === 0) return false
  if (orphanConstinuations.length > 0) return false
  for (const list of problems.values()) {
    if (list.some((p) => p.type === 'chybi-kod' || p.type.startsWith('duplicitni-kod'))) {
      return false
    }
  }
  return true
}
