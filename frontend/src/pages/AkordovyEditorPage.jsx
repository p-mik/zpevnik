import { useParams, Link } from 'react-router-dom'
import { useApiResource } from '../hooks/useApiResource'
import { useAkordovyEditor } from '../akordy/useAkordovyEditor'
import { useVarovaniPriOdchodu } from '../pdf/useAnotace'
import AkordovyHlavicka from '../akordy/AkordovyHlavicka'
import AkordovyMrizka from '../akordy/AkordovyMrizka'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import '../components/ui.css'
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

  return (
    <div className="akordy-editor-page">
      <Link to={verze.pisen ? `/pisne/${verze.pisen}` : '/pisne'} className="breadcrumb-back">
        ← Zpět na píseň
      </Link>

      <h1 className="section-heading">
        Akordový zápis{song ? ` — ${song.nazev}` : ''}
        {verze.cislo ? ` · Verze ${verze.cislo}` : ''}
      </h1>

      <AkordovyHlavicka
        takt={editor.zapis.takt}
        tempo={editor.zapis.tempo}
        sekce={editor.zapis.sekce}
        onZmenTakt={editor.nastavTakt}
        onZmenTempo={editor.nastavTempo}
      />

      <AkordovyMrizka
        zapis={editor.zapis}
        onUpravBunku={editor.upravBunku}
        onNastavNazevSekce={editor.nastavNazevSekce}
        onPridejTakt={editor.pridejTakt}
        onSmazTakt={editor.smazTakt}
        onSmazRadek={editor.smazRadek}
        onVlozRadekPo={editor.vlozRadekPo}
        onSmazSekci={editor.smazSekci}
        onPridejSekci={editor.pridejSekci}
        onPridejRepetici={editor.pridejRepetici}
        onSmazRepetici={editor.smazRepetici}
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

      {verze.ma_soubor && (
        <div className="akordy-editor-odkazy">
          <Link to={`/pisne/${verze.pisen}/ctecka?verze=${verze.id}`} className="btn btn-secondary">
            Otevřít ve čtečce
          </Link>
          <a href={`/api/verze-pisni/${verze.id}/soubor/`} className="btn btn-secondary">
            Stáhnout PDF
          </a>
        </div>
      )}
    </div>
  )
}
