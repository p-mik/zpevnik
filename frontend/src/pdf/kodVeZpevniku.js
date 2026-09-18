// Kód písně je od fáze 2b vlastnost zařazení do KONKRÉTNÍHO zpěvníku, ne
// písně samotné (viz PolozkaZpevniku na backendu) — stejná píseň může mít
// v různých zpěvnících různá čísla. `song.zarazeni` (z PisenDetailSerializer)
// je seznam všech takových zařazení; tahle funkce z něj vytáhne číslo PRO
// KONKRÉTNÍ zpěvník, když je jasné, o který jde (typicky z `?z=` v URL).
// Bez zpevnikId (nebo když v něm píseň není) vrací null — appka pak
// jednoduše nezobrazí žádný odznak, místo aby hádala.
export function kodVeZpevniku(song, zpevnikId) {
  return zarazeniVeZpevniku(song, zpevnikId)?.kod ?? null
}

// Totéž, ale celá položka zařazení (i název zpěvníku) — pro nenápadný
// popisek "ve kterém zpěvníku jsem" ve čtečce/stage módu.
export function zarazeniVeZpevniku(song, zpevnikId) {
  if (!zpevnikId || !song?.zarazeni) return null
  return song.zarazeni.find((z) => String(z.zpevnik) === String(zpevnikId)) || null
}
