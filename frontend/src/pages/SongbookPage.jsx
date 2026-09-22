import { Link, useParams } from 'react-router-dom'
import { useApiResource } from '../hooks/useApiResource'
import { useAuth } from '../auth/AuthContext'
import SongRow, { SongList } from '../components/SongRow'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import EmptyState from '../components/EmptyState'
import '../components/ui.css'
import './SongbookPage.css'

export default function SongbookPage() {
  const { id } = useParams()
  const { user } = useAuth()
  const { data: zpevnik, loading, error, reload } = useApiResource(`/api/zpevniky/${id}/`)

  if (loading) return <LoadingState label="Načítám zpěvník…" />
  if (error) {
    return (
      <ErrorState
        message={error.status === 404 ? 'Tenhle zpěvník neexistuje.' : 'Zpěvník se nepodařilo načíst.'}
        onRetry={error.status === 404 ? undefined : reload}
      />
    )
  }

  return (
    <div>
      <Link className="breadcrumb-back" to={zpevnik.slozka ? `/slozky/${zpevnik.slozka}` : '/slozky'}>
        ← Zpět
      </Link>

      <div className="songbook-head">
        <h1 className="section-heading">{zpevnik.nazev}</h1>
        <div className="songbook-head-akce">
          <Link to={`/zpevniky/${id}/nova-pisen-akordy`} className="btn btn-secondary">
            + Nová píseň z akordů
          </Link>
          {user?.role === 'admin' && (
            <Link to={`/import?zpevnik=${id}`} className="btn btn-secondary">
              Import PDF
            </Link>
          )}
        </div>
      </div>

      {zpevnik.pisne.length === 0 ? (
        <EmptyState
          title="Tenhle zpěvník zatím nemá žádné písně"
          description="Písně se do zpěvníku přiřazují přes administraci."
          actionLabel="Otevřít administraci"
          actionHref="/admin/"
        />
      ) : (
        <SongList>
          {zpevnik.pisne.map((song) => (
            <SongRow key={song.id} song={song} zpevnikId={id} />
          ))}
        </SongList>
      )}
    </div>
  )
}
