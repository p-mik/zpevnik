import { Link, Navigate, useParams, useSearchParams } from 'react-router-dom'
import { useApiResource } from '../hooks/useApiResource'
import { useReaderAuth } from '../pdf/useReaderAuth'
import { resolveVerze } from '../pdf/resolveVerze'
import { useSongNavigation } from '../pdf/useSongNavigation'
import StageView from '../pdf/StageView'
import LoadingState from '../components/LoadingState'
import '../pdf/StageView.css'

export default function StageModePage() {
  const auth = useReaderAuth()
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const zpevnikId = searchParams.get('z')
  const backHref = `/pisne/${id}`

  const { data: song, loading, error } = useApiResource(auth.status === 'ready' ? `/api/pisne/${id}/` : null)
  const { prevSong, nextSong } = useSongNavigation(id, zpevnikId)

  if (auth.status === 'loading') return <LoadingState label="Ověřuji přihlášení…" />
  if (auth.status === 'redirect') return <Navigate to="/prihlaseni" replace state={{ from: auth.from }} />

  if (loading) {
    return (
      <div className="stage-root stage-root-static">
        <span className="stage-loading">Načítám píseň…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="stage-root stage-root-static">
        <div className="stage-unavailable">
          <h2>{error.status === 404 ? 'Tahle píseň neexistuje' : 'Nepodařilo se načíst'}</h2>
          <Link to={backHref} className="stage-btn">
            Zpět
          </Link>
        </div>
      </div>
    )
  }

  const pozadovaneId = Number(searchParams.get('verze'))
  const { currentVerze, unavailableTitle, unavailableMessage } = resolveVerze(song, pozadovaneId)

  const zSuffix = zpevnikId ? `?z=${zpevnikId}` : ''

  return (
    <StageView
      pdfPath={currentVerze ? `/api/verze-pisni/${currentVerze.id}/soubor/` : null}
      unavailableTitle={unavailableTitle}
      unavailableMessage={unavailableMessage}
      title={song.nazev}
      codeLabel={String(song.kod).padStart(3, '0')}
      exitHref={backHref}
      sessionLost={auth.sessionLost}
      prevSongHref={prevSong ? `/pisne/${prevSong.id}/stage${zSuffix}` : undefined}
      nextSongHref={nextSong ? `/pisne/${nextSong.id}/stage${zSuffix}` : undefined}
      pickerHrefFor={(song) => `/pisne/${song.id}/stage${zSuffix}`}
      currentSongId={song.id}
    />
  )
}
