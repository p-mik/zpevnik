import { IkonaNadpis, IkonaPridatSekci, IkonaRepetice, IkonaTakt, IkonaVolta } from './AkordyIkony'
import './AkordovyToolbar.css'

// Toolbar (docs/zadani_redesign_akordovy_zapis.md bod 2) — nahrazuje
// dřívější fixní lištu u levého okraje okna (PC_zpevnik_akordy_ovladani.md
// bod 6). Vodorovný pruh, `position: sticky; top: 0`, ve stejném normálním
// toku jako zbytek stránky — proto taky odpadá celá dřívější viewport-
// relativní matematika na odsazení kolem fixní lišty (viz AkordovyMrizka.css
// a AkordovyEditorPage.css). Skupina 1 (Repetice/Volta/Takt) je bez výběru
// `disabled`, NE skrytá — stejný důvod jako dřív: lišta nemá měnit tvar
// podle stavu výběru.
export default function AkordovyToolbar({
  vyberAktivni,
  onRepetice,
  onVolta,
  onTakt,
  onPridejSekci,
  onPridejSekciBezRadku,
}) {
  return (
    <div className="akordy-toolbar" role="toolbar" aria-label="Akce akordového zápisu">
      <button
        type="button"
        className="akordy-toolbar-btn"
        onClick={onRepetice}
        disabled={!vyberAktivni}
        title="Repetice (vyber takty)"
      >
        <IkonaRepetice width={20} height={16} />
        Repetice
      </button>
      <button
        type="button"
        className="akordy-toolbar-btn"
        onClick={onVolta}
        disabled={!vyberAktivni}
        title="Volta (vyber takty)"
      >
        <IkonaVolta size={16} />
        Volta
      </button>
      <button
        type="button"
        className="akordy-toolbar-btn"
        onClick={onTakt}
        disabled={!vyberAktivni}
        title="Změnit takt od vybraných taktů"
      >
        <IkonaTakt size={16} />
        Takt
      </button>

      <span className="akordy-toolbar-oddelovac" aria-hidden="true" />

      <button type="button" className="akordy-toolbar-btn" onClick={onPridejSekci}>
        <IkonaPridatSekci size={16} />
        Sekce
      </button>
      <button
        type="button"
        className="akordy-toolbar-btn"
        onClick={onPridejSekciBezRadku}
        title="Sekce jen s nadpisem, bez taktů — třeba „Sloka 2 = Sloka 1“."
      >
        <IkonaNadpis size={16} />
        Nadpis
      </button>

      <div className="akordy-toolbar-mezera" />

      <div className="akordy-toolbar-napoveda">
        <span>
          <kbd>Tab</kbd> další buňka
        </span>
        <span>
          <kbd>Enter</kbd> nový řádek
        </span>
        <span>
          <kbd>⌫</kbd> spojí s předchozím
        </span>
      </div>
    </div>
  )
}
