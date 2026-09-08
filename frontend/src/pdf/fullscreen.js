// Fullscreen API vyžaduje, aby `requestFullscreen()` běžel přímo uvnitř
// obsluhy gesta uživatele (kliknutí) — proto se volá synchronně z onClick
// odkazu na stage mode, ne z useEffectu až po přenavigování. Prohlížeč,
// který to nepodporuje (typicky iPad Safari mimo desktop-class režim),
// slib jen tiše odmítne — stage mode dál funguje na CSS fullscreen (viz
// StageModePage.css), Fullscreen API je jen bonus navíc (schová chrome
// prohlížeče).
export function requestDocumentFullscreen() {
  try {
    document.documentElement.requestFullscreen?.().catch(() => {})
  } catch {
    // některé prohlížeče můžou hodit synchronně, ne jen odmítnout promise
  }
}

export function exitDocumentFullscreen() {
  try {
    if (document.fullscreenElement) {
      document.exitFullscreen?.().catch(() => {})
    }
  } catch {
    // exit nevyžaduje gesto, ale radši nenechat vyjímku spadnout do cleanupu
  }
}
