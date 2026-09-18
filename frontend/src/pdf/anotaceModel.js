// Tvar jednoho objektu anotační vrstvy (v1 = jen textové pole).
// Souřadnice jsou ZLOMKY rozměru stránky (0–1), nikdy pixely: tytéž poznámky
// se čtou na PC i na tabletu, při zoomu a po otočení displeje. Totéž hlídá
// i server (viz AnotaceObjektSerializer).

export const STYLY = [
  { hodnota: 'normal', popisek: 'Poznámka' },
  { hodnota: 'mono', popisek: 'Tab / rytmus' },
  { hodnota: 'akord', popisek: 'Akord' },
  { hodnota: 'znacka', popisek: 'Značka' },
]

export const VELIKOSTI = [
  { hodnota: 'mala', popisek: 'Malé' },
  { hodnota: 'normalni', popisek: 'Střední' },
  { hodnota: 'velka', popisek: 'Velké' },
]

export const VYCHOZI_VELIKOST = 'normalni'

export const PREDVOLBY_ZNACEK = ['REF', 'SL.', 'SPECIAL', 'BRIDGE', 'CODA']

export const MIN_SIRKA = 0.03
export const VYCHOZI_SIRKA = 0.2

export function omez(hodnota, min, max) {
  return Math.min(max, Math.max(min, hodnota))
}

export function novaAnotace(strana, x, y) {
  return {
    // crypto.randomUUID chybí na starším Safari i mimo secure context —
    // id musí být jen unikátní v rámci jedné verze, takže tohle stačí.
    id: `a-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    strana,
    x: omez(x, 0, 1 - VYCHOZI_SIRKA),
    y: omez(y, 0, 0.98),
    sirka: VYCHOZI_SIRKA,
    text: '',
    styl: 'normal',
    velikost: VYCHOZI_VELIKOST,
  }
}
