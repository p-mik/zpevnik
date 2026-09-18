import { PREDVOLBY_ZNACEK, STYLY, VELIKOSTI, VYCHOZI_VELIKOST } from './anotaceModel'
import './AnnotationToolbar.css'

// Lišta režimu úprav. Vlevo co se dá dělat, vpravo uložení — výslovné, se
// stavem „neuloženo", ne autosave při každém písmenu.
//
// Typ poznámky je vidět a přepínatelný VŽDY, i bez vybraného pole — funguje
// jako nástroj v kreslicím programu: zvolí se jednou a dvojklik do not pak
// zakládá pole rovnou s ním, místo aby vznikalo pořád jako "poznámka" a styl
// se dolaďoval až dodatečně po každém vložení. Když je něco vybrané, tlačítko
// zároveň přebarví i to pole — jedna akce, dvě role podle kontextu.
export default function AnnotationToolbar({
  vybrany,
  typProNove,
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
  const aktivniStyl = vybrany ? vybrany.styl : typProNove

  return (
    <div className="anotace-lista">
      <div className="anotace-lista-nastroje">
        <div className="anotace-styly" role="group" aria-label="Typ poznámky">
          {STYLY.map((styl) => (
            <button
              key={styl.hodnota}
              type="button"
              className={`anotace-styl${aktivniStyl === styl.hodnota ? ' anotace-styl-aktivni' : ''}`}
              onClick={() => onStyl(styl.hodnota)}
              aria-pressed={aktivniStyl === styl.hodnota}
            >
              {styl.popisek}
            </button>
          ))}
        </div>

        {vybrany ? (
          <>
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
            Dvojklik do not vloží pole zvoleného typu. Klik ho vybere, tažení posune, dvojklik otevře text.
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
