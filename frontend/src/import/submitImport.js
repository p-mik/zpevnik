import { api } from '../api/client'

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
    cely_zpevnik: celyZpevnik ? { nazev: celyZpevnik.nazev, vytvorit: celyZpevnik.vytvorit } : null,
  }
}

export async function submitImport(file, songs, kategorie, celyZpevnik) {
  const formData = new FormData()
  formData.append('soubor', file)
  formData.append('plan', JSON.stringify(buildPlanPayload(songs, kategorie, celyZpevnik)))
  return api.post('/api/import/', formData, { isFormData: true })
}
