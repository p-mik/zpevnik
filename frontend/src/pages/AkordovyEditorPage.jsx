import { useParams, Link } from 'react-router-dom'
import { useApiResource } from '../hooks/useApiResource'
import { useAkordovyEditor } from '../akordy/useAkordovyEditor'
import { useVarovaniPriOdchodu } from '../pdf/useAnotace'
import { IkonaZpet } from '../akordy/AkordyIkony'
import { jmenoSouboruExportu, jsonExportu, stahniText } from '../akordy/akordyExport'
import AkordovyHlavicka from '../akordy/AkordovyHlavicka'
import AkordovyMrizka from '../akordy/AkordovyMrizka'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import '../components/ui.css'
// Redesign editoru (docs/zadani_redesign_akordovy_zapis.md) potřebuje IBM
// Plex Sans/Mono navíc k fontům, co appka jinak sama-hostuje (Oswald/Work
// Sans/JetBrains Mono, viz main.jsx) — schválně natažené TADY, ne v
// main.jsx, ať je platí jen tahle stránka, ne celá appka.
import '@fontsource/ibm-plex-sans/latin-400.css'
import '@fontsource/ibm-plex-sans/latin-ext-400.css'
import '@fontsource/ibm-plex-sans/latin-500.css'
import '@fontsource/ibm-plex-sans/latin-ext-500.css'
import '@fontsource/ibm-plex-sans/latin-600.css'
import '@fontsource/ibm-plex-sans/latin-ext-600.css'
import '@fontsource/ibm-plex-mono/latin-500.css'
import '@fontsource/ibm-plex-mono/latin-ext-500.css'
import './AkordovyEditorPage.css'

// Editor akordového zápisu (viz PC_zpevnik_akordovy_zapis.md, fáze 2).
// Vstup vždy přes konkrétní VerzePisne se zdroj=akordy — nová verze se
// založí ještě PŘED příchodem sem (viz tlačítka "Nová akordová verze" na
// SongDetailPage a formulář na NovaPisenZAkordyPage), tahle stránka jen
// edituje a ukládá, ať se nemusí řešit "ještě neexistuje" jako zvláštní stav.
export default function AkordovyEditorPage() {
  const { verzeId } = useParams()
  const { data: verze, loading: nacitamVerzi, error: chybaVerze, reload: reloadVerze } = useApiResource(
    `/api/verze-pisni/${verzeId}/`,
  )
  const { data: song } = useApiResource(verze ? `/api/pisne/${verze.pisen}/` : null)
  const editor = useAkordovyEditor(verzeId)

  useVarovaniPriOdchodu(editor.zmeneno)

  if (nacitamVerzi || editor.nacitam) return <LoadingState label="Načítám akordový zápis…" />
  if (chybaVerze || editor.chyba) {
    return (
      <ErrorState
        message={
          chybaVerze?.status === 404
            ? 'Tahle verze neexistuje.'
            : editor.chyba || 'Akordový zápis se nepodařilo načíst.'
        }
      />
    )
  }
  if (verze.zdroj !== 'akordy') {
    return <ErrorState message="Tahle verze nemá akordový zápis — je to nahrané PDF." />
  }

  async function ulozit() {
    const ok = await editor.uloz()
    if (ok) reloadVerze()
  }

  function exportovatJson() {
    stahniText(jmenoSouboruExportu(song?.nazev, verze.cislo), jsonExportu(editor.zapis))
  }

  return (
    <div className="akordy-editor-page">
      <div className="akordy-editor-hlavicka-radek">
        <div className="akordy-editor-zpet-nadpis">
          <Link to={verze.pisen ? `/pisne/${verze.pisen}` : '/pisne'} className="akordy-zpet-odkaz">
            <IkonaZpet size={14} />
            Zpět na píseň
          </Link>
          <div className="akordy-editor-nadpis-radek">
            <h1 className="akordy-editor-nazev">{song ? song.nazev : 'Akordový zápis'}</h1>
            <span className="akordy-editor-meta">
              Akordový zápis{verze.cislo ? ` · Verze ${verze.cislo}` : ''}
            </span>
          </div>
        </div>

        <AkordovyHlavicka
          takt={editor.zapis.takt}
          tempo={editor.zapis.tempo}
          sekce={editor.zapis.sekce}
          onZmenTakt={editor.nastavTakt}
          onZmenTempo={editor.nastavTempo}
        />
      </div>

      <AkordovyMrizka
        zapis={editor.zapis}
        onUpravBunku={editor.upravBunku}
        onNastavNazevSekce={editor.nastavNazevSekce}
        onPridejTakt={editor.pridejTakt}
        onSmazTakt={editor.smazTakt}
        onVlozRadekPo={editor.vlozRadekPo}
        onRozdelRadek={editor.rozdelRadek}
        onSpojRadek={editor.spojRadek}
        onSmazSekci={editor.smazSekci}
        onPridejSekci={editor.pridejSekci}
        onPridejSekciBezRadku={editor.pridejSekciBezRadku}
        onRozdelSekci={editor.rozdelSekci}
        onSpojSePredchozi={editor.spojSePredchozi}
        onPosunSekci={editor.posunSekci}
        onDuplikujSekci={editor.duplikuj}
        onPridejRepetici={editor.pridejRepetici}
        onSmazRepetici={editor.smazRepetici}
        onPridejVoltu={editor.pridejVoltu}
        onSmazVoltu={editor.smazVoltu}
        onZmenTaktVyberu={editor.zmenTaktVyberu}
      />

      <div className="akordy-editor-ulozeni">
        {editor.chyba && (
          <span className="akordy-editor-chyba" role="alert">
            {editor.chyba}
          </span>
        )}
        <span className={`akordy-editor-stav${editor.zmeneno ? ' akordy-editor-stav-zmeneno' : ''}`}>
          {editor.ukladam ? 'Ukládám…' : editor.zmeneno ? 'Neuloženo' : 'Uloženo'}
        </span>
        <button
          type="button"
          className="btn btn-primary"
          onClick={ulozit}
          disabled={editor.ukladam || !editor.zmeneno}
        >
          Uložit
        </button>
      </div>

      {editor.pocetAnotaciKtereMohlyUjet > 0 && (
        <p className="akordy-editor-anotace-varovani" role="status">
          Tahle verze má {editor.pocetAnotaciKtereMohlyUjet}{' '}
          {editor.pocetAnotaciKtereMohlyUjet === 1 ? 'poznámku' : 'poznámek'}, změna rozložení je
          může posunout.
        </p>
      )}

      <div className="akordy-editor-odkazy">
        {/* Export bere to, co je PRÁVĚ v editoru (tedy i neuložené změny —
            stav "Uloženo/Neuloženo" je hned vedle), ne to, co je na
            serveru: data už jsou v prohlížeči, takže se nemusí nikam
            chodit. Na rozdíl od PDF je dostupný vždycky, i když verze
            ještě nemá vygenerovaný soubor. */}
        <button type="button" className="btn btn-secondary" onClick={exportovatJson}>
          Exportovat JSON
        </button>
        {verze.ma_soubor && (
          <>
            <Link to={`/pisne/${verze.pisen}/ctecka?verze=${verze.id}`} className="btn btn-secondary">
              Otevřít ve čtečce
            </Link>
            <a href={`/api/verze-pisni/${verze.id}/soubor/`} className="btn btn-secondary">
              Stáhnout PDF
            </a>
          </>
        )}
      </div>
    </div>
  )
}
