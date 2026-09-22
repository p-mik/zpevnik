import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useApiResource } from '../hooks/useApiResource'
import { useGlobalSongNavigation } from '../pdf/useSongNavigation'
import { STAV_LABELS, TYP_OBSAHU_LABELS } from '../constants'
import { api } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import '../components/ui.css'
import './SongDetailPage.css'

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
  const { data: song, loading, error, reload } = useApiResource(`/api/pisne/${id}/`)
  // Listování napříč VŠÍM podle jména — tahle stránka je rozcestník mezi
  // zpěvníky, ne slepá ulička, do které se člověk dostane a musí zpátky přes
  // menu. Čtečka/stage mode naopak listují v rámci jednoho zpěvníku podle
  // kódu (viz useSongNavigation) — jiný účel, jiný hook.
  const { prevSong, nextSong } = useGlobalSongNavigation(id)
  const [zakladamAkordy, setZakladamAkordy] = useState(false)
  const [chybaAkordy, setChybaAkordy] = useState(null)

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
          </div>
          {chybaAkordy && (
            <p className="akordy-editor-chyba" role="alert">
              {chybaAkordy}
            </p>
          )}
        </div>
      </div>

      <h2>Verze ({song.verze.length})</h2>
      {song.verze.length === 0 ? (
        <p>Tahle píseň zatím nemá nahranou žádnou verzi.</p>
      ) : (
        <ul className="verze-list">
          {song.verze.map((verze) => (
            <li key={verze.id} className="verze-row">
              <div className="verze-text">
                <span className="stav-label">
                  {STAV_LABELS[verze.stav] || verze.stav}
                  {song.aktivni_verze && verze.id === song.aktivni_verze.id && (
                    <span className="active-badge">Aktivní</span>
                  )}
                </span>
                <span className="verze-info">
                  {verze.zdroj === 'akordy' ? 'Akordový zápis' : TYP_OBSAHU_LABELS[verze.typ_obsahu] || verze.typ_obsahu}
                  {verze.vlastnik && ` · ${verze.vlastnik.username}`}
                  {!verze.ma_soubor && ' · bez souboru'}
                </span>
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
