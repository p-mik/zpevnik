import { useEffect, useState } from 'react'
import { jeDotykove, jeStandalone } from './displayMode'
import './StageInstallHint.css'

const KLIC = 'zpevnik.stage-install-hint'
const AUTO_HIDE_MS = 9000

// localStorage umí házet (Safari v privátním režimu, zakázaná data stránek),
// a nápověda rozhodně není důvod, proč by měl spadnout stage mode.
function bylaOdbyta() {
  try {
    return window.localStorage.getItem(KLIC) === 'ok'
  } catch {
    return false
  }
}

function zapamatuj() {
  try {
    window.localStorage.setItem(KLIC, 'ok')
  } catch {
    // nevadí — nápověda se příště ukáže znovu, nic horšího
  }
}

// Jednorázová nápověda: v prohlížeči zůstává nad notami lišta, kterou stage
// mode nemá jak schovat (Fullscreen API iOS pro dokument nenabízí). Ukáže se
// jen na dotykovém zařízení, jen když appka neběží standalone, a po odbytí
// už nikdy. Na desktopu se plocha nepoužívá a lištu tam schová fullscreen,
// takže by tam rada jen překážela přes noty.
export default function StageInstallHint() {
  const [visible, setVisible] = useState(
    () => jeDotykove() && !jeStandalone() && !bylaOdbyta(),
  )

  useEffect(() => {
    if (!visible) return
    const timer = setTimeout(() => {
      zapamatuj()
      setVisible(false)
    }, AUTO_HIDE_MS)
    return () => clearTimeout(timer)
  }, [visible])

  if (!visible) return null

  function odbyt(e) {
    e.stopPropagation()
    zapamatuj()
    setVisible(false)
  }

  return (
    // stopPropagation: ťuknutí do nápovědy nesmí zároveň otočit stránku not.
    <div className="stage-hint" role="status" onClick={(e) => e.stopPropagation()}>
      <p className="stage-hint-text">
        Pro celou obrazovku si přidej appku na plochu.
        <span className="stage-hint-note">V prohlížeči zůstane nahoře jeho lišta.</span>
      </p>
      <button type="button" className="stage-hint-dismiss" onClick={odbyt}>
        Rozumím
      </button>
    </div>
  )
}
