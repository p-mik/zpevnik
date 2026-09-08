// API vrací syrové kódy (`stav`, `typ_obsahu`) — popisky jsou stejné jako
// v zpevnik/models.py STAV_CHOICES / TYP_OBSAHU_CHOICES, jen na jednom místě.
export const STAV_LABELS = {
  draft: 'Koncept',
  download: 'Stažené',
  confirmed: 'Potvrzené',
  handmade: 'Ručně vyrobené',
  personal: 'Osobní',
}

export const TYP_OBSAHU_LABELS = {
  pdf: 'PDF',
  text: 'Text',
}
