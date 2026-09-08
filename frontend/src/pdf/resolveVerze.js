// Sdílená logika mezi běžnou čtečkou a stage mode: která verze se má
// otevřít (z URL, jinak server-vybraná aktivní, jinak první se souborem)
// a srozumitelná hláška, když noty prostě nejsou k dispozici.
export function resolveVerze(song, requestedId) {
  const dostupne = song.verze.filter((v) => v.ma_soubor)
  const zPozadavku = dostupne.find((v) => v.id === requestedId)
  const currentVerze = zPozadavku || dostupne.find((v) => v.id === song.aktivni_verze?.id) || dostupne[0] || null

  let unavailableTitle = null
  let unavailableMessage = null
  if (song.verze.length === 0) {
    unavailableTitle = 'Bez verze'
    unavailableMessage = 'Tahle píseň zatím nemá nahranou žádnou verzi.'
  } else if (!currentVerze) {
    unavailableTitle = 'Bez souboru'
    unavailableMessage = 'Žádná verze týhle písně nemá nahraný soubor s notami.'
  } else if (currentVerze.typ_obsahu !== 'pdf') {
    unavailableTitle = 'Zatím nepodporováno'
    unavailableMessage = 'Tenhle typ obsahu čtečka zatím nezobrazí — jen PDF.'
  }

  return { currentVerze, dostupne, unavailableTitle, unavailableMessage }
}

// Veřejná píseň nemá `verze` pole ani `ma_soubor` — server pošle rovnou
// `aktivni_verze` (jen typ_obsahu) a `soubor_url` (null, když nic není).
export function resolvePublicVerze(song) {
  if (!song.aktivni_verze) {
    return { unavailableTitle: 'Bez verze', unavailableMessage: 'Tahle píseň zatím nemá žádnou verzi.' }
  }
  if (song.aktivni_verze.typ_obsahu !== 'pdf') {
    return {
      unavailableTitle: 'Zatím nepodporováno',
      unavailableMessage: 'Tenhle typ obsahu čtečka zatím nezobrazí — jen PDF.',
    }
  }
  if (!song.soubor_url) {
    return { unavailableTitle: 'Bez souboru', unavailableMessage: 'Tahle píseň nemá veřejně dostupné noty.' }
  }
  return { unavailableTitle: null, unavailableMessage: null }
}
