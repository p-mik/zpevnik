// Export akordového zápisu do .json.
//
// Obsahem souboru je PŘESNĚ to, co appka ukládá (schéma 2: schema/takt/
// tempo/sekce) — nic víc. Díky tomu se dá soubor poslat rovnou zpátky do
// `POST /api/pisne/{id}/verze-akordy/` v těle `{"akordy": <obsah>}` a
// založit z něj novou verzi (viz api_views.PisenViewSet.verze_akordy).
// Metadata písně (název, číslo verze) se proto do JSONu NEPŘIDÁVAJÍ —
// AkordovyZapisSerializer je nezná a jen by kazily round-trip; identita
// souboru jde do jeho NÁZVU.

const NAHRADNI_ZAKLAD = 'akordy'
// Delší název souboru nic nezkazí, ale je nepraktický — a některé cloudy
// a FAT32 flashky na dlouhých jménech pořád padají.
const MAX_DELKA_ZAKLADU = 60

// "Raising my family" -> "raising-my-family", "Přes Údolí!" -> "pres-udoli".
// NFD + odstranění kombinujících znaků řeší diakritiku bez tabulky výjimek.
function slug(text) {
  const bezDiakritiky = String(text || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
  return bezDiakritiky
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, MAX_DELKA_ZAKLADU)
    .replace(/-+$/g, '')
}

export function jmenoSouboruExportu(nazevPisne, cisloVerze) {
  const zaklad = slug(nazevPisne) || NAHRADNI_ZAKLAD
  const verze = Number.isFinite(Number(cisloVerze)) && Number(cisloVerze) > 0
    ? `-verze-${Number(cisloVerze)}`
    : ''
  return `${zaklad}${verze}.json`
}

// Odsazené, ať je soubor čitelný i v editoru; koncový newline kvůli
// nástrojům, co si na něj potrpí (diff, git).
export function jsonExportu(zapis) {
  return `${JSON.stringify(zapis, null, 2)}\n`
}

// Stažení souboru z dat, co už jsou v prohlížeči — žádný request na server.
export function stahniText(jmenoSouboru, text, typ = 'application/json') {
  const url = URL.createObjectURL(new Blob([text], { type: `${typ};charset=utf-8` }))
  const odkaz = document.createElement('a')
  odkaz.href = url
  odkaz.download = jmenoSouboru
  document.body.appendChild(odkaz)
  odkaz.click()
  odkaz.remove()
  // Uvolnit až po kliknutí — při okamžitém revoke stáhne Safari prázdný soubor.
  setTimeout(() => URL.revokeObjectURL(url), 0)
}
