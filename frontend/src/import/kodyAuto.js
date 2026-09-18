// Kód není povinný — dopočítá se. Písně bez kódu (parser ho nenašel, nebo ho
// uživatel v tabulce smazal) dostanou číslo v POŘADÍ STRAN, počínaje buď
// ručně zadaným počátkem ("Kódy od"), nebo další volnou stovkou nad
// nejvyšším kódem v databázi. Ručně zadaný/parsovaný kód má vždy přednost —
// tahle funkce se ho nikdy nedotkne, jen DOPLŇUJE chybějící.

// Prázdné "Kódy od" = další volná stovka nad nejvyšším kódem v DB. Prázdná
// DB (nový zpěvník) začíná na 100 — stovka je konvence, kterou drží i
// ŠUBAPS zpěvník (101–529).
export function dalsiVolnaStovka(existingKody) {
  if (!existingKody || existingKody.size === 0) return 100
  const max = Math.max(...existingKody)
  return (Math.floor(max / 100) + 1) * 100
}

// `kodyOd` je číslo, nebo null/undefined (= použij dalsiVolnaStovka).
// Nikdy nekoliduje s DB ani s kódem, co si v tomhle importu ručně zadal
// někdo jiný — kandidát na přiřazení přeskakuje všechny už použité hodnoty.
export function prirazKody(songs, kodyOd, existingKody) {
  const pouzite = new Set(existingKody || [])
  for (const s of songs) {
    if (s.kod != null) pouzite.add(s.kod)
  }

  let kandidat = Number.isInteger(kodyOd) && kodyOd > 0 ? kodyOd : dalsiVolnaStovka(existingKody)

  return songs.map((s) => {
    if (s.kod != null) return s
    while (pouzite.has(kandidat)) kandidat += 1
    pouzite.add(kandidat)
    return { ...s, kod: kandidat, kodOdhad: true }
  })
}
