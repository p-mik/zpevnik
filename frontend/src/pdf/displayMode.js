// Běží appka jako samostatná (přidaná na plochu), nebo v prohlížeči s lištou?
// Chrome/Edge/Android to hlásí přes media query, iOS Safari jen přes vlastní
// `navigator.standalone` — manifest sám o sobě neznamená, že appka standalone
// běží, takže se musí ptát obojího.
// Ovládá se zařízení hlavně prstem? `pointer: coarse` mluví o primárním
// vstupu, ne o tom, co zařízení umí — dotykový notebook s trackpadem hlásí
// `fine`, a tam je rada „přidej si to na plochu“ k ničemu. Proto ne
// `any-pointer` ani maxTouchPoints, ty by ho chytly taky.
export function jeDotykove() {
  if (typeof window === 'undefined') return false
  try {
    return window.matchMedia('(pointer: coarse)').matches
  } catch {
    return false
  }
}

export function jeStandalone() {
  if (typeof window === 'undefined') return false
  if (window.navigator.standalone === true) return true
  try {
    return window.matchMedia('(display-mode: standalone), (display-mode: fullscreen)').matches
  } catch {
    return false
  }
}
