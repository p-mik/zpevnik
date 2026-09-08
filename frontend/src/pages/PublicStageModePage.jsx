import { Link, useParams } from 'react-router-dom'
import { useApiResource } from '../hooks/useApiResource'
import { resolvePublicVerze } from '../pdf/resolveVerze'
import StageView from '../pdf/StageView'
import '../pdf/StageView.css'

export default function PublicStageModePage() {
  const { token, kod } = useParams()
  const backHref = `/verejny/${token}/pisen/${kod}`
  const { data: zpevnik, loading, error } = useApiResource(`/api/verejny/${token}/`)

  if (loading) {
    return (
      <div className="stage-root stage-root-static">
        <span className="stage-loading">Načítám…</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="stage-root stage-root-static">
        <div className="stage-unavailable">
          <h2>{error.status === 404 ? 'Odkaz neplatí' : 'Nepodařilo se načíst'}</h2>
          <Link to={`/verejny/${token}`} className="stage-btn">
            Zpět na zpěvník
          </Link>
        </div>
      </div>
    )
  }

  const song = zpevnik.pisne.find((p) => String(p.kod) === kod)
  if (!song) {
    return (
      <div className="stage-root stage-root-static">
        <div className="stage-unavailable">
          <h2>Píseň nenalezena</h2>
          <Link to={`/verejny/${token}`} className="stage-btn">
            Zpět na zpěvník
          </Link>
        </div>
      </div>
    )
  }

  const { unavailableTitle, unavailableMessage } = resolvePublicVerze(song)

  return (
    <StageView
      pdfPath={song.soubor_url}
      unavailableTitle={unavailableTitle}
      unavailableMessage={unavailableMessage}
      title={song.nazev}
      codeLabel={String(song.kod).padStart(3, '0')}
      exitHref={backHref}
    />
  )
}
