import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useApiResource } from '../hooks/useApiResource'
import { useAuth } from '../auth/AuthContext'
import { api } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import SongRow, { SongList } from '../components/SongRow'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import EmptyState from '../components/EmptyState'
import ConfirmDeleteDialog from '../components/ConfirmDeleteDialog'
import '../components/ui.css'
import './SongbookPage.css'

export default function SongbookPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
  const { data: zpevnik, loading, error, reload } = useApiResource(`/api/zpevniky/${id}/`)

  const [nahledMazani, setNahledMazani] = useState(null)
  const [mazani, setMazani] = useState(false)
  const [chybaMazani, setChybaMazani] = useState(null)

  if (loading) return <LoadingState label="Načítám zpěvník…" />
  if (error) {
    return (
      <ErrorState
        message={error.status === 404 ? 'Tenhle zpěvník neexistuje.' : 'Zpěvník se nepodařilo načíst.'}
        onRetry={error.status === 404 ? undefined : reload}
      />
    )
  }

  async function otevritSmazani() {
    setChybaMazani(null)
    try {
      const nahled = await api.get(`/api/zpevniky/${id}/smazat-nahled/`)
      setNahledMazani(nahled)
    } catch (err) {
      setChybaMazani(extractErrorMessage(err, 'Náhled smazání se nepodařilo načíst.'))
    }
  }

  async function smazatZpevnik() {
    setMazani(true)
    setChybaMazani(null)
    try {
      await api.delete(`/api/zpevniky/${id}/`)
      navigate(zpevnik.slozka ? `/slozky/${zpevnik.slozka}` : '/slozky', { replace: true })
    } catch (err) {
      setChybaMazani(extractErrorMessage(err, 'Zpěvník se nepodařilo smazat.'))
      setMazani(false)
    }
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
            <>
              <Link to={`/import?zpevnik=${id}`} className="btn btn-secondary">
                Import PDF
              </Link>
              <button type="button" className="btn songbook-smazat-btn" onClick={otevritSmazani}>
                Smazat zpěvník
              </button>
            </>
          )}
        </div>
      </div>

      {chybaMazani && !nahledMazani && (
        <p className="akordy-editor-chyba" role="alert">
          {chybaMazani}
        </p>
      )}

      {nahledMazani && (
        <ConfirmDeleteDialog
          title={`Smazat zpěvník „${zpevnik.nazev}“?`}
          nazev={zpevnik.nazev}
          mazani={mazani}
          chyba={chybaMazani}
          onPotvrdit={smazatZpevnik}
          onZrusit={() => setNahledMazani(null)}
        >
          <p>Nevratně zmizí:</p>
          <ul>
            <li>
              {nahledMazani.pisni_zmizi}{' '}
              {nahledMazani.pisni_zmizi === 1 ? 'píseň, která je' : 'písní, které jsou'} jen v
              tomhle zpěvníku (i s verzemi, soubory a poznámkami)
            </li>
            {nahledMazani.setlisty > 0 && (
              <li>
                položky z těchhle písní v {nahledMazani.setlisty}{' '}
                {nahledMazani.setlisty === 1 ? 'setlistu' : 'setlistech'}
              </li>
            )}
          </ul>
          {nahledMazani.pisni_zustane > 0 && (
            <p>
              {nahledMazani.pisni_zustane}{' '}
              {nahledMazani.pisni_zustane === 1 ? 'píseň zůstane' : 'písní zůstane'} — je/jsou i v
              jiném zpěvníku.
            </p>
          )}
        </ConfirmDeleteDialog>
      )}

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
