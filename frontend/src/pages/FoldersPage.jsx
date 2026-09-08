import { Link, useParams } from 'react-router-dom'
import { useAllPages } from '../hooks/useAllPages'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import EmptyState from '../components/EmptyState'
import '../components/ui.css'

export default function FoldersPage() {
  const { id } = useParams()
  const currentId = id ? Number(id) : null

  const {
    data: slozky,
    loading: loadingSlozky,
    error: errorSlozky,
    reload: reloadSlozky,
  } = useAllPages('/api/slozky/')
  const {
    data: zpevniky,
    loading: loadingZpevniky,
    error: errorZpevniky,
    reload: reloadZpevniky,
  } = useAllPages('/api/zpevniky/')

  const loading = loadingSlozky || loadingZpevniky
  const error = errorSlozky || errorZpevniky

  if (loading) return <LoadingState label="Načítám zpěvníky…" />
  if (error) {
    return (
      <ErrorState
        message="Zpěvníky se nepodařilo načíst."
        onRetry={() => {
          reloadSlozky()
          reloadZpevniky()
        }}
      />
    )
  }

  const currentFolder = currentId ? slozky.find((s) => s.id === currentId) : null
  if (currentId && !currentFolder) {
    return <ErrorState message="Tahle složka neexistuje." />
  }

  const subfolders = slozky.filter((s) => (s.rodic ?? null) === currentId)
  const songbooksHere = zpevniky.filter((z) => (z.slozka ?? null) === currentId)
  const isEmpty = subfolders.length === 0 && songbooksHere.length === 0

  return (
    <div>
      {currentFolder && (
        <Link
          className="breadcrumb-back"
          to={currentFolder.rodic ? `/slozky/${currentFolder.rodic}` : '/slozky'}
        >
          ← Zpět
        </Link>
      )}

      <h1 className="section-heading">{currentFolder ? currentFolder.nazev : 'Složky'}</h1>

      {isEmpty && (
        <EmptyState
          title="Tady zatím nic není"
          description="Složky a zpěvníky se zakládají přes administraci."
          actionLabel="Otevřít administraci"
          actionHref="/admin/"
        />
      )}

      {subfolders.length > 0 && (
        <ul className="link-list">
          {subfolders.map((slozka) => (
            <li key={`s-${slozka.id}`}>
              <Link className="link-row" to={`/slozky/${slozka.id}`}>
                <span className="nazev">{slozka.nazev}</span>
                <span className="count">složka</span>
              </Link>
            </li>
          ))}
        </ul>
      )}

      {songbooksHere.length > 0 && (
        <ul className="link-list">
          {songbooksHere.map((zpevnik) => (
            <li key={`z-${zpevnik.id}`}>
              <Link className="link-row" to={`/zpevniky/${zpevnik.id}`}>
                <span className="nazev">{zpevnik.nazev}</span>
                <span className="count">{zpevnik.pisne.length} písní</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
