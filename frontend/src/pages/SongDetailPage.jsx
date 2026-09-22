import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useApiResource } from '../hooks/useApiResource'
import { useGlobalSongNavigation } from '../pdf/useSongNavigation'
import { useAuth } from '../auth/AuthContext'
import { STAV_LABELS, TYP_OBSAHU_LABELS } from '../constants'
import { api } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import { popisekCasuVerze } from '../utils/datum'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import ConfirmDeleteDialog from '../components/ConfirmDeleteDialog'
import '../components/ui.css'
import './SongDetailPage.css'

// Aktivní verze vždy první, zbytek podle nejnovější úpravy (to už appka
// dostane z API — VerzePisne.Meta.ordering je "-upraveno", viz zadání bod
// 5: "nejnovější úprava nahoře, aktivní verze vždy první").
function verzeSerazene(song) {
  if (!song.aktivni_verze) return song.verze
  const aktivni = song.verze.find((v) => v.id === song.aktivni_verze.id)
  if (!aktivni) return song.verze
  return [aktivni, ...song.verze.filter((v) => v.id !== aktivni.id)]
}

function SousedniPisen({ pisen, smer }) {
  const popisek = smer === 'predchozi' ? 'Předchozí' : 'Další'
  if (!pisen) {
    return (
      <span className="btn song-nav-btn" aria-disabled="true">
        {smer === 'predchozi' ? `‹ ${popisek}` : `${popisek} ›`}
      </span>
    )
  }
  // Bez kódu schválně — tohle je procházení napříč VŠÍM, ne v rámci
  // jednoho zpěvníku, a kód je od fáze 2b vlastnost zařazení do
  // konkrétního zpěvníku, ne písně (viz PolozkaZpevniku). Řadí se podle
  // jména (useSongNavigation), tak se jméno i ukazuje.
  return (
    <Link to={`/pisne/${pisen.id}`} className="btn song-nav-btn">
      {smer === 'predchozi' && '‹ '}
      <span className="song-nav-nazev">{pisen.nazev}</span>
      {smer === 'dalsi' && ' ›'}
    </Link>
  )
}

export default function SongDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { data: song, loading, error, reload } = useApiResource(`/api/pisne/${id}/`)
  // Listování napříč VŠÍM podle jména — tahle stránka je rozcestník mezi
  // zpěvníky, ne slepá ulička, do které se člověk dostane a musí zpátky přes
  // menu. Čtečka/stage mode naopak listují v rámci jednoho zpěvníku podle
  // kódu (viz useSongNavigation) — jiný účel, jiný hook.
  const { prevSong, nextSong } = useGlobalSongNavigation(id)
  const [zakladamAkordy, setZakladamAkordy] = useState(false)
  const [chybaAkordy, setChybaAkordy] = useState(null)
  const [importujiMusicXml, setImportujiMusicXml] = useState(false)

  const [nahledMazani, setNahledMazani] = useState(null)
  const [mazani, setMazani] = useState(false)
  const [chybaMazani, setChybaMazani] = useState(null)

  if (loading) return <LoadingState label="Načítám píseň…" />
  if (error) {
    return (
      <ErrorState
        message={error.status === 404 ? 'Tahle píseň neexistuje.' : 'Píseň se nepodařilo načíst.'}
        onRetry={error.status === 404 ? undefined : reload}
      />
    )
  }

  const maNejakySoubor = song.verze.some((v) => v.ma_soubor)

  async function novaAkordovaVerze() {
    setZakladamAkordy(true)
    setChybaAkordy(null)
    try {
      const verze = await api.post(`/api/pisne/${song.id}/verze-akordy/`)
      navigate(`/verze-pisni/${verze.id}/akordy`)
    } catch (err) {
      setChybaAkordy(extractErrorMessage(err, 'Akordovou verzi se nepodařilo založit.'))
      setZakladamAkordy(false)
    }
  }

  async function importMusicXml(e) {
    const soubor = e.target.files?.[0]
    e.target.value = ''
    if (!soubor) return
    setImportujiMusicXml(true)
    setChybaAkordy(null)
    try {
      const formData = new FormData()
      formData.append('soubor', soubor)
      const verze = await api.post(`/api/pisne/${song.id}/verze-musicxml/`, formData, {
        isFormData: true,
      })
      navigate(`/verze-pisni/${verze.id}/akordy`)
    } catch (err) {
      setChybaAkordy(extractErrorMessage(err, 'MusicXML se nepodařilo naimportovat.'))
      setImportujiMusicXml(false)
    }
  }

  async function otevritSmazani() {
    setChybaMazani(null)
    try {
      const nahled = await api.get(`/api/pisne/${song.id}/smazat-nahled/`)
      setNahledMazani(nahled)
    } catch (err) {
      setChybaMazani(extractErrorMessage(err, 'Náhled smazání se nepodařilo načíst.'))
    }
  }

  async function smazatPisen() {
    setMazani(true)
    setChybaMazani(null)
    try {
      await api.delete(`/api/pisne/${song.id}/`)
      navigate('/pisne', { replace: true })
    } catch (err) {
      setChybaMazani(extractErrorMessage(err, 'Píseň se nepodařilo smazat.'))
      setMazani(false)
    }
  }

  return (
    <div className="song-detail-page">
      <nav className="song-detail-nav" aria-label="Procházení písní">
        <SousedniPisen pisen={prevSong} smer="predchozi" />
        <Link to="/pisne" className="song-nav-seznam">
          Seznam písní
        </Link>
        <SousedniPisen pisen={nextSong} smer="dalsi" />
      </nav>

      <div className="song-detail-head">
        <div>
          <h1>{song.nazev}</h1>
          {song.interpret && <p className="interpret">{song.interpret}</p>}
          {song.zarazeni?.length > 0 && (
            <ul className="song-zarazeni" aria-label="Číslo v jednotlivých zpěvnících">
              {song.zarazeni.map((z) => (
                <li key={z.id}>
                  <Link to={`/pisne/${song.id}/ctecka?z=${z.zpevnik}`} className="song-zarazeni-item">
                    <span className="code-chip">{String(z.kod).padStart(3, '0')}</span>
                    <span className="song-zarazeni-nazev">{z.zpevnik_nazev}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <dl className="song-meta">
            {song.tonina && (
              <span>
                <dt>Tónina</dt>
                <dd>{song.tonina}</dd>
              </span>
            )}
            {song.capo != null && (
              <span>
                <dt>Capo</dt>
                <dd>{song.capo}</dd>
              </span>
            )}
            {song.tempo != null && (
              <span>
                <dt>Tempo</dt>
                <dd>{song.tempo} BPM</dd>
              </span>
            )}
            {song.odkaz_nahravka && (
              <span>
                <dt>Nahrávka</dt>
                <dd>
                  <a href={song.odkaz_nahravka} target="_blank" rel="noreferrer">
                    otevřít ↗
                  </a>
                </dd>
              </span>
            )}
          </dl>
          <div className="song-detail-akce">
            {maNejakySoubor && (
              <Link to={`/pisne/${song.id}/ctecka`} className="btn btn-primary song-open-btn">
                Otevřít noty
              </Link>
            )}
            <button
              type="button"
              className="btn btn-secondary"
              onClick={novaAkordovaVerze}
              disabled={zakladamAkordy}
            >
              {zakladamAkordy ? 'Zakládám…' : 'Nová akordová verze'}
            </button>
            <label className="btn btn-secondary song-musicxml-label">
              {importujiMusicXml ? 'Importuji…' : 'Import MusicXML'}
              <input
                type="file"
                accept=".musicxml,.xml"
                onChange={importMusicXml}
                disabled={importujiMusicXml}
                className="song-musicxml-input"
              />
            </label>
            {user?.role === 'admin' && (
              <button type="button" className="btn song-smazat-btn" onClick={otevritSmazani}>
                Smazat píseň
              </button>
            )}
          </div>
          {chybaAkordy && (
            <p className="akordy-editor-chyba" role="alert">
              {chybaAkordy}
            </p>
          )}
          {chybaMazani && !nahledMazani && (
            <p className="akordy-editor-chyba" role="alert">
              {chybaMazani}
            </p>
          )}
        </div>
      </div>

      {nahledMazani && (
        <ConfirmDeleteDialog
          title={`Smazat píseň „${song.nazev}“?`}
          nazev={song.nazev}
          mazani={mazani}
          chyba={chybaMazani}
          onPotvrdit={smazatPisen}
          onZrusit={() => setNahledMazani(null)}
        >
          <p>Nevratně zmizí:</p>
          <ul>
            <li>
              {nahledMazani.verzi} {nahledMazani.verzi === 1 ? 'verze' : 'verze/verzí'} (i se
              soubory)
            </li>
            <li>{nahledMazani.anotaci} {nahledMazani.anotaci === 1 ? 'poznámka' : 'poznámek'}</li>
            <li>
              zařazení ve {nahledMazani.zpevniky.length}{' '}
              {nahledMazani.zpevniky.length === 1 ? 'zpěvníku' : 'zpěvnících'}
              {nahledMazani.zpevniky.length > 0 && `: ${nahledMazani.zpevniky.join(', ')}`}
            </li>
            {nahledMazani.setlisty > 0 && (
              <li>
                položka v {nahledMazani.setlisty}{' '}
                {nahledMazani.setlisty === 1 ? 'setlistu' : 'setlistech'} (setlist samotný zůstane)
              </li>
            )}
          </ul>
        </ConfirmDeleteDialog>
      )}

      <h2>Verze ({song.verze.length})</h2>
      {song.verze.length === 0 ? (
        <p>Tahle píseň zatím nemá nahranou žádnou verzi.</p>
      ) : (
        <ul className="verze-list">
          {verzeSerazene(song).map((verze) => (
            <li key={verze.id} className="verze-row">
              <div className="verze-text">
                <span className="stav-label">
                  {/* Číslo verze — bez něj v detailu nejde poznat, která
                      verze je která (viz PC_zpevnik_akordovy_zapis_upravy.md
                      bod 5). Nepřečíslovává se po smazání starších verzí. */}
                  {verze.cislo != null ? `Verze ${verze.cislo}` : 'Verze'} ·{' '}
                  {STAV_LABELS[verze.stav] || verze.stav} ·{' '}
                  {verze.zdroj === 'akordy' ? 'Akordový zápis' : TYP_OBSAHU_LABELS[verze.typ_obsahu] || verze.typ_obsahu}
                  {verze.vlastnik && ` · ${verze.vlastnik.username}`}
                  {song.aktivni_verze && verze.id === song.aktivni_verze.id && (
                    <span className="active-badge">Aktivní</span>
                  )}
                </span>
                <span className="verze-cas">{popisekCasuVerze(verze.vytvoreno, verze.upraveno)}</span>
                {!verze.ma_soubor && <span className="verze-info">bez souboru</span>}
              </div>
              <div className="verze-row-akce">
                {verze.zdroj === 'akordy' && (
                  <Link to={`/verze-pisni/${verze.id}/akordy`} className="btn verze-open-btn">
                    Upravit akordy
                  </Link>
                )}
                {verze.ma_soubor && (
                  <Link to={`/pisne/${song.id}/ctecka?verze=${verze.id}`} className="btn verze-open-btn">
                    Otevřít
                  </Link>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
