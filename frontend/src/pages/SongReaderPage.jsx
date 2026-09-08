import { Navigate, useParams, useSearchParams } from 'react-router-dom'
import { useApiResource } from '../hooks/useApiResource'
import { useReaderAuth } from '../pdf/useReaderAuth'
import { resolveVerze } from '../pdf/resolveVerze'
import ReaderView from '../pdf/ReaderView'
import VersionSwitcher from '../pdf/VersionSwitcher'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'

export default function SongReaderPage() {
  const auth = useReaderAuth()
  const { id } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()

  const { data: song, loading, error, reload } = useApiResource(auth.status === 'ready' ? `/api/pisne/${id}/` : null)

  if (auth.status === 'loading') return <LoadingState label="Ověřuji přihlášení…" />
  if (auth.status === 'redirect') {
    return <Navigate to="/prihlaseni" replace state={{ from: auth.from }} />
  }

  if (loading) return <LoadingState label="Načítám píseň…" />
  if (error) {
    return (
      <ErrorState
        message={error.status === 404 ? 'Tahle píseň neexistuje.' : 'Píseň se nepodařilo načíst.'}
        onRetry={error.status === 404 ? undefined : reload}
      />
    )
  }

  const pozadovaneId = Number(searchParams.get('verze'))
  const { currentVerze, unavailableTitle, unavailableMessage } = resolveVerze(song, pozadovaneId)

  return (
    <ReaderView
      pdfPath={currentVerze ? `/api/verze-pisni/${currentVerze.id}/soubor/` : null}
      unavailableTitle={unavailableTitle}
      unavailableMessage={unavailableMessage}
      backHref={`/pisne/${id}`}
      backLabel="Zpět na píseň"
      codeLabel={String(song.kod).padStart(3, '0')}
      title={song.nazev}
      subtitle={song.interpret}
      sessionBanner={auth.sessionLost}
      versionSwitcher={
        <VersionSwitcher
          verze={song.verze}
          currentId={currentVerze?.id}
          onChange={(verzeId) => setSearchParams({ verze: String(verzeId) })}
        />
      }
      stageHref={currentVerze ? `/pisne/${id}/stage?verze=${currentVerze.id}` : undefined}
    />
  )
}
