import { useParams } from 'react-router-dom'
import { useApiResource } from '../hooks/useApiResource'
import { STAV_LABELS, TYP_OBSAHU_LABELS } from '../constants'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import '../components/ui.css'
import './SongDetailPage.css'

export default function SongDetailPage() {
  const { id } = useParams()
  const { data: song, loading, error, reload } = useApiResource(`/api/pisne/${id}/`)

  if (loading) return <LoadingState label="Načítám píseň…" />
  if (error) {
    return (
      <ErrorState
        message={error.status === 404 ? 'Tahle píseň neexistuje.' : 'Píseň se nepodařilo načíst.'}
        onRetry={error.status === 404 ? undefined : reload}
      />
    )
  }

  return (
    <div className="song-detail-page">
      <div className="song-detail-head">
        <span className="code-chip">{String(song.kod).padStart(3, '0')}</span>
        <div>
          <h1>{song.nazev}</h1>
          {song.interpret && <p className="interpret">{song.interpret}</p>}
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
        </div>
      </div>

      <h2>Verze ({song.verze.length})</h2>
      {song.verze.length === 0 ? (
        <p>Tahle píseň zatím nemá nahranou žádnou verzi.</p>
      ) : (
        <ul className="verze-list">
          {song.verze.map((verze) => (
            <li key={verze.id} className="verze-row">
              <span className="stav-label">
                {STAV_LABELS[verze.stav] || verze.stav}
                {song.aktivni_verze && verze.id === song.aktivni_verze.id && (
                  <span className="active-badge">Aktivní</span>
                )}
              </span>
              <span className="verze-info">
                {TYP_OBSAHU_LABELS[verze.typ_obsahu] || verze.typ_obsahu}
                {verze.vlastnik && ` · ${verze.vlastnik.username}`}
                {!verze.ma_soubor && ' · bez souboru'}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
