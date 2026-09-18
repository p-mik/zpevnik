// Fullscreen API vyžaduje, aby `requestFullscreen()` běžel přímo uvnitř
// obsluhy gesta uživatele (kliknutí) — proto se volá synchronně z onClick
// odkazu na stage mode, ne z useEffectu až po přenavigování.
//
// Je to vědomě jen pokus navíc, na kterém nic nestojí: iPad Safari ho mimo
// desktop-class režim odmítne a iPhone Safari ho pro dokument nemá vůbec.
// Skutečné schování lišty prohlížeče na iOS obstará až „Přidat na plochu“
// (viz manifest + apple-mobile-web-app-capable v index.html), stage mode sám
// stojí na CSS fullscreenu a funguje i bez jednoho i druhého.
//
// Starší WebKit používá prefix a na rozdíl od standardu nevrací promise —
// proto `?.catch?.()`, ne `.catch()`.
export function requestDocumentFullscreen() {
  const el = document.documentElement
  const request =
    el.requestFullscreen || el.webkitRequestFullscreen || el.webkitRequestFullScreen
  try {
    request?.call(el)?.catch?.(() => {})
  } catch {
    // některé prohlížeče můžou hodit synchronně, ne jen odmítnout promise
  }
}

export function exitDocumentFullscreen() {
  const exit = document.exitFullscreen || document.webkitExitFullscreen
  try {
    if (document.fullscreenElement || document.webkitFullscreenElement) {
      exit?.call(document)?.catch?.(() => {})
    }
  } catch {
    // exit nevyžaduje gesto, ale radši nenechat výjimku spadnout do cleanupu
  }
}
