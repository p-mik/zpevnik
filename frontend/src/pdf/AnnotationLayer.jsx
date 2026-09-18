import { useEffect, useRef, useState } from 'react'
import { isTypingTarget } from './usePagingKeys'
import { MIN_SIRKA, VYCHOZI_VELIKOST, omez } from './anotaceModel'
import './AnnotationLayer.css'

// Textarea začíná na jeden řádek (viz rows={1} a bez min-height v CSS) a
// roste s obsahem — ne napevno na dva řádky předem. `height: auto` před
// změřením je nutné, jinak by scrollHeight při MAZÁNÍ textu zůstal
// zaklíněný na předchozí (větší) výšce. Volá se jak z ref callbacku (velikost
// hned při otevření pole — i pro už rozepsaný víceřádkový text), tak z
// onChange (přerůst/zmenšení při psaní). Je to obyčejná funkce mimo
// komponentu, ne hook — nevadí, že se používá z ref i z event handleru.
function velikostTextarea(el) {
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${el.scrollHeight}px`
}

// Vrstva poznámek nad jednou stránkou PDF. Leží v `.pdf-page-stack`, který má
// přesně rozměr vykreslené stránky, takže zlomkové souřadnice stačí přepsat
// na procenta a sedí samy — při zoomu, na jiné šířce okna i po otočení tabletu.
//
// `varianta` přepíná paletu: 'app' (čtečka, papír + inkoust) vs. 'stage'
// (tmavá deska, --stage-anotace-*). Ve stage módu se jen zobrazuje.
export default function AnnotationLayer({
  objekty,
  varianta = 'app',
  editovatelne = false,
  vybranyId = null,
  onVybrat,
  onVytvorit,
  onZmenit,
  onSmazat,
}) {
  const vrstvaRef = useRef(null)
  const tahRef = useRef(null)
  const [editovanyId, setEditovanyId] = useState(null)
  const textPredEditaciRef = useRef('')

  // Delete maže vybrané pole — ale ne když se zrovna píše do textu, tam je to
  // obyčejná klávesa.
  useEffect(() => {
    if (!editovatelne || !vybranyId || editovanyId) return undefined
    function naKlavesu(e) {
      if (e.key !== 'Delete') return
      if (isTypingTarget(e.target)) return
      e.preventDefault()
      onSmazat?.(vybranyId)
    }
    window.addEventListener('keydown', naKlavesu)
    return () => window.removeEventListener('keydown', naKlavesu)
  }, [editovatelne, vybranyId, editovanyId, onSmazat])

  // Při odchodu z režimu úprav skonči i rozepsanou editaci textu.
  useEffect(() => {
    if (!editovatelne) setEditovanyId(null)
  }, [editovatelne])

  function zlomkyZUdalosti(e) {
    const rect = vrstvaRef.current.getBoundingClientRect()
    return {
      x: (e.clientX - rect.left) / rect.width,
      y: (e.clientY - rect.top) / rect.height,
    }
  }

  function naDvojklikDoPrazdna(e) {
    if (!editovatelne) return
    // Jen prázdné místo — dvojklik na poli otevírá editaci jeho textu.
    if (e.target !== vrstvaRef.current) return
    const { x, y } = zlomkyZUdalosti(e)
    onVytvorit?.(x, y)
  }

  function zacniTah(e, objekt, druh) {
    if (!editovatelne || editovanyId === objekt.id) return
    e.preventDefault()
    e.stopPropagation()
    const vrstva = vrstvaRef.current.getBoundingClientRect()
    const pole = e.currentTarget.closest('.anotace').getBoundingClientRect()
    tahRef.current = {
      druh,
      id: objekt.id,
      sirkaVrstvy: vrstva.width,
      vyskaVrstvy: vrstva.height,
      startX: e.clientX,
      startY: e.clientY,
      puvodni: { x: objekt.x, y: objekt.y, sirka: objekt.sirka },
      // Výška pole je daná obsahem, ne uloženou hodnotou — aby pole nešlo
      // vytáhnout spodní hranou pod stránku, musí se změřit teď.
      vyskaZlomek: pole.height / vrstva.height,
    }
    e.currentTarget.setPointerCapture?.(e.pointerId)
    onVybrat?.(objekt.id)
  }

  function naTah(e) {
    const tah = tahRef.current
    if (!tah) return
    const dx = (e.clientX - tah.startX) / tah.sirkaVrstvy
    const dy = (e.clientY - tah.startY) / tah.vyskaVrstvy

    if (tah.druh === 'posun') {
      onZmenit?.(tah.id, {
        x: omez(tah.puvodni.x + dx, 0, 1 - tah.puvodni.sirka),
        y: omez(tah.puvodni.y + dy, 0, Math.max(0, 1 - tah.vyskaZlomek)),
      })
    } else {
      onZmenit?.(tah.id, {
        sirka: omez(tah.puvodni.sirka + dx, MIN_SIRKA, 1 - tah.puvodni.x),
      })
    }
  }

  function ukonciTah(e) {
    if (!tahRef.current) return
    e.currentTarget.releasePointerCapture?.(e.pointerId)
    tahRef.current = null
  }

  function zacniEditaciTextu(objekt) {
    if (!editovatelne) return
    textPredEditaciRef.current = objekt.text
    setEditovanyId(objekt.id)
  }

  function naKlavesuVText(e, objekt) {
    if (e.key === 'Escape') {
      // Ruší se editace textu, ne celý režim úprav — proto stopPropagation.
      e.stopPropagation()
      onZmenit?.(objekt.id, { text: textPredEditaciRef.current })
      setEditovanyId(null)
    }
  }

  return (
    <div
      ref={vrstvaRef}
      className={`anotace-vrstva anotace-${varianta}${editovatelne ? ' anotace-editor' : ''}`}
      onDoubleClick={naDvojklikDoPrazdna}
    >
      {objekty.map((objekt) => {
        const vybrane = editovatelne && objekt.id === vybranyId
        const edituje = editovanyId === objekt.id
        return (
          <div
            key={objekt.id}
            className={`anotace${vybrane ? ' anotace-vybrana' : ''}`}
            data-styl={objekt.styl}
            // Starší poznámky velikost nemají — ty zůstávají na střední.
            data-velikost={objekt.velikost || VYCHOZI_VELIKOST}
            style={{
              left: `${objekt.x * 100}%`,
              top: `${objekt.y * 100}%`,
              width: `${objekt.sirka * 100}%`,
            }}
            onPointerDown={(e) => zacniTah(e, objekt, 'posun')}
            onPointerMove={naTah}
            onPointerUp={ukonciTah}
            onPointerCancel={ukonciTah}
            onDoubleClick={(e) => {
              e.stopPropagation()
              zacniEditaciTextu(objekt)
            }}
          >
            {edituje ? (
              <textarea
                className="anotace-text-input"
                value={objekt.text}
                rows={1}
                ref={velikostTextarea}
                autoFocus
                onChange={(e) => {
                  onZmenit?.(objekt.id, { text: e.target.value })
                  velikostTextarea(e.target)
                }}
                onKeyDown={(e) => naKlavesuVText(e, objekt)}
                onBlur={() => setEditovanyId(null)}
                onPointerDown={(e) => e.stopPropagation()}
                aria-label="Text poznámky"
                // iPad: appka vlastní pravopis/kapitalizaci/autokorekci nechce —
                // text bývá akord, tab nebo zkratka, kde by "opravy" jen škodily.
                autoCorrect="off"
                autoCapitalize="off"
                spellCheck={false}
              />
            ) : (
              <span className="anotace-text">{objekt.text || (editovatelne ? '…' : '')}</span>
            )}

            {vybrane && !edituje && (
              <span
                className="anotace-uchyt"
                role="presentation"
                onPointerDown={(e) => zacniTah(e, objekt, 'sirka')}
                onPointerMove={naTah}
                onPointerUp={ukonciTah}
                onPointerCancel={ukonciTah}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
