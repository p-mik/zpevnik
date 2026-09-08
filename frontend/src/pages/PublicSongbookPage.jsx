import { Link, useParams } from 'react-router-dom'
import { useApiResource } from '../hooks/useApiResource'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import '../components/ui.css'
import './PublicSongbookPage.css'

// Samostatná stránka bez přihlášení — žádná hlavička, žádné menu, žádné API
// volání, které by cokoliv předpokládalo o session.
export default function PublicSongbookPage() {
  const { token } = useParams()
  const { data: zpevnik, loading, error, reload } = useApiResource(`/api/verejny/${token}/`)

  if (loading) {
    return (
      <div className="public-wrap">
        <LoadingState label="Načítám zpěvník…" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="public-wrap">
        <ErrorState
          message={
            error.status === 404
              ? 'Tenhle odkaz neexistuje nebo už neplatí.'
              : 'Zpěvník se nepodařilo načíst.'
          }
          onRetry={error.status === 404 ? undefined : reload}
        />
      </div>
    )
  }

  return (
    <div className="public-wrap">
      <div className="public-header">
        <span className="eyebrow">Veřejný zpěvník</span>
        <h1>{zpevnik.nazev}</h1>
      </div>

      {zpevnik.pisne.length === 0 ? (
        <p>Tenhle zpěvník zatím nemá žádné písně.</p>
      ) : (
        <div className="panel">
          {zpevnik.pisne.map((song) => (
            <div className="public-song-row" key={song.kod}>
              <span className="code-chip">{String(song.kod).padStart(3, '0')}</span>
              <span className="titles">
                <span className="nazev">{song.nazev}</span>
                {song.interpret && <span className="interpret">{song.interpret}</span>}
              </span>
              {song.soubor_url && (
                <Link className="pdf-link" to={`/verejny/${token}/pisen/${song.kod}`}>
                  Noty
                </Link>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
