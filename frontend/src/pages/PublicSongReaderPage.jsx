import { useParams } from 'react-router-dom'
import { useApiResource } from '../hooks/useApiResource'
import { resolvePublicVerze } from '../pdf/resolveVerze'
import ReaderView from '../pdf/ReaderView'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'

// Bez přihlášení — stejné zobrazení jako běžná čtečka, jen bez přepínání
// verzí (server sám vybírá jedinou veřejně dostupnou) a bez věcí, co
// předpokládají uživatele (žádný sessionBanner, žádné useReaderAuth).
export default function PublicSongReaderPage() {
  const { token, kod } = useParams()
  const { data: zpevnik, loading, error, reload } = useApiResource(`/api/verejny/${token}/`)

  if (loading) return <LoadingState label="Načítám zpěvník…" />
  if (error) {
    return (
      <ErrorState
        message={error.status === 404 ? 'Tenhle odkaz neexistuje nebo už neplatí.' : 'Zpěvník se nepodařilo načíst.'}
        onRetry={error.status === 404 ? undefined : reload}
      />
    )
  }

  const song = zpevnik.pisne.find((p) => String(p.kod) === kod)
  if (!song) {
    return <ErrorState message="Tahle píseň v tomhle zpěvníku není." />
  }

  const { unavailableTitle, unavailableMessage } = resolvePublicVerze(song)

  return (
    <ReaderView
      pdfPath={song.soubor_url}
      unavailableTitle={unavailableTitle}
      unavailableMessage={unavailableMessage}
      backHref={`/verejny/${token}`}
      backLabel="Zpět na zpěvník"
      codeLabel={String(song.kod).padStart(3, '0')}
      title={song.nazev}
      subtitle={song.interpret}
      stageHref={song.soubor_url ? `/verejny/${token}/pisen/${kod}/stage` : undefined}
    />
  )
}
