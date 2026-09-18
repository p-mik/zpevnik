import { PREDVOLBY_ZNACEK, STYLY, VELIKOSTI, VYCHOZI_VELIKOST } from './anotaceModel'
import './AnnotationToolbar.css'

// Lišta režimu úprav. Vlevo co se dá dělat s vybraným polem, vpravo uložení —
// výslovné, se stavem „neuloženo", ne autosave při každém písmenu.
export default function AnnotationToolbar({
  vybrany,
  onStyl,
  onVelikost,
  onText,
  onSmazat,
  onKonec,
  onUlozit,
  zmeneno,
  ukladam,
  chyba,
}) {
  return (
    <div className="anotace-lista">
      <div className="anotace-lista-nastroje">
        {vybrany ? (
          <>
            <div className="anotace-styly" role="group" aria-label="Styl poznámky">
              {STYLY.map((styl) => (
                <button
                  key={styl.hodnota}
                  type="button"
                  className={`anotace-styl${vybrany.styl === styl.hodnota ? ' anotace-styl-aktivni' : ''}`}
                  onClick={() => onStyl(styl.hodnota)}
                  aria-pressed={vybrany.styl === styl.hodnota}
                >
                  {styl.popisek}
                </button>
              ))}
            </div>
            <div className="anotace-styly" role="group" aria-label="Velikost písma">
              {VELIKOSTI.map((velikost) => {
                const aktivni = (vybrany.velikost || VYCHOZI_VELIKOST) === velikost.hodnota
                return (
                  <button
                    key={velikost.hodnota}
                    type="button"
                    className={`anotace-styl${aktivni ? ' anotace-styl-aktivni' : ''}`}
                    onClick={() => onVelikost(velikost.hodnota)}
                    aria-pressed={aktivni}
                  >
                    {velikost.popisek}
                  </button>
                )
              })}
            </div>
            {vybrany.styl === 'znacka' && (
              <div className="anotace-predvolby" role="group" aria-label="Předvolby značek">
                {PREDVOLBY_ZNACEK.map((text) => (
                  <button
                    key={text}
                    type="button"
                    className="anotace-predvolba"
                    onClick={() => onText(text)}
                  >
                    {text}
                  </button>
                ))}
              </div>
            )}
            <button type="button" className="anotace-smazat" onClick={onSmazat}>
              Smazat
            </button>
          </>
        ) : (
          <p className="anotace-napoveda">
            Dvojklik do not založí poznámku. Klik ji vybere, tažení posune, dvojklik otevře text.
          </p>
        )}
      </div>

      <div className="anotace-lista-ulozeni">
        {chyba && (
          <span className="anotace-chyba" role="alert">
            {chyba}
          </span>
        )}
        <span className={`anotace-stav${zmeneno ? ' anotace-stav-zmeneno' : ''}`}>
          {ukladam ? 'Ukládám…' : zmeneno ? 'Neuloženo' : 'Uloženo'}
        </span>
        <button
          type="button"
          className="btn btn-primary anotace-ulozit"
          onClick={onUlozit}
          disabled={ukladam || !zmeneno}
        >
          Uložit
        </button>
        <button type="button" className="btn btn-secondary anotace-konec" onClick={onKonec}>
          Hotovo
        </button>
      </div>
    </div>
  )
}
