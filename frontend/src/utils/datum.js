// Formátování času verze v detailu písně (viz
// PC_zpevnik_akordovy_zapis_upravy.md bod 5) — Europe/Prague bez ohledu na
// časové pásmo prohlížeče, ať se admin z jiného pásma nedivil.

const FORMAT = new Intl.DateTimeFormat('cs-CZ', {
  timeZone: 'Europe/Prague',
  day: 'numeric',
  month: 'numeric',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

function formatujDatumCas(iso) {
  return FORMAT.format(new Date(iso))
}

// Když se vytvoření a poslední úprava liší o míň než minutu, ukázat jen
// "vytvořeno" — jinak by "upraveno" jen zbytečně opakovalo skoro totéž.
export function popisekCasuVerze(vytvoreno, upraveno) {
  if (!vytvoreno) return '—'
  const text = `vytvořeno ${formatujDatumCas(vytvoreno)}`
  if (!upraveno) return text
  const rozdilMs = Math.abs(new Date(upraveno) - new Date(vytvoreno))
  if (rozdilMs < 60000) return text
  return `${text} · upraveno ${formatujDatumCas(upraveno)}`
}
