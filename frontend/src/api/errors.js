import { ApiError } from './client'

// DRF vrací chyby polí zanořené (`{soubor: ["...", ...]}`, někdy o patro víž).
// Pro hlášku u tlačítka je potřeba jedna věta, ne strom.
function zplostiChybu(hodnota) {
  if (typeof hodnota === 'string') return [hodnota]
  if (Array.isArray(hodnota)) return hodnota.flatMap(zplostiChybu)
  if (hodnota && typeof hodnota === 'object') return Object.values(hodnota).flatMap(zplostiChybu)
  return [String(hodnota)]
}

export function extractErrorMessage(err, nahradni = 'Něco se nepovedlo.') {
  if (!(err instanceof ApiError)) return nahradni
  if (err.detail) return err.detail
  if (err.fieldErrors) return zplostiChybu(err.fieldErrors).join(' ') || nahradni
  return nahradni
}
