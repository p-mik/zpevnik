import { api } from '../api/client'

// Cíl importu (PC_zpevnik_sprava.md bod 4) je POVINNÝ — buď existující
// zpěvník (mod: 'existujici', vybraný podle ID, ne podle jména — jméno by
// se mohlo shodovat náhodou), nebo nový (mod: 'novy', s názvem).
export function buildPlanPayload(songs, kategorie, celyZpevnik) {
  return {
    pisne: songs.map((s) => ({
      kod: s.kod,
      nazev: s.nazev,
      interpret: s.interpret,
      stranky: s.stranky,
    })),
    kategorie: kategorie.map((k) => ({
      digit: k.digit,
      nazev: k.nazev,
      vytvorit: k.vytvorit,
    })),
    cely_zpevnik:
      celyZpevnik.mod === 'existujici'
        ? { existujici_id: celyZpevnik.existujiciId }
        : { nazev: celyZpevnik.nazev },
  }
}

export async function submitImport(file, songs, kategorie, celyZpevnik) {
  const formData = new FormData()
  formData.append('soubor', file)
  formData.append('plan', JSON.stringify(buildPlanPayload(songs, kategorie, celyZpevnik)))
  return api.post('/api/import/', formData, { isFormData: true })
}
