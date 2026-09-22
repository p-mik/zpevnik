import { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { useApiResource } from '../hooks/useApiResource'
import { api } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import '../components/ui.css'
import './NovaPisenZAkordyPage.css'

const CHYBA = 'Píseň se nepodařilo založit.'

// "Nová píseň z akordů" ze stránky zpěvníku (viz PC_zpevnik_akordovy_zapis.md
// fáze 2) — založí píseň, zařadí ji do TOHOTO zpěvníku pod zadaným kódem a
// rovnou otevře editor prázdné akordové verze. Tři API volání za sebou
// (píseň → zařazení → verze) nejsou v jedné transakci: při kolizi kódu
// (vzácné, návrh z dalsi-kod je čerstvý) píseň už existuje, jen bez
// zařazení — dá se dohotovit později, appka to nezkouší tiše řešit rollbackem.
export default function NovaPisenZAkordyPage() {
  const { zpevnikId } = useParams()
  const navigate = useNavigate()
  const { data: zpevnik, loading: nacitamZpevnik, error: chybaZpevnik } = useApiResource(
    `/api/zpevniky/${zpevnikId}/`,
  )
  const { data: navrh } = useApiResource(`/api/zpevniky/${zpevnikId}/dalsi-kod/`)

  const [nazev, setNazev] = useState('')
  const [interpret, setInterpret] = useState('')
  const [kod, setKod] = useState('')
  const [zaklada, setZaklada] = useState(false)
  const [chyba, setChyba] = useState(null)

  useEffect(() => {
    if (navrh?.kod != null && kod === '') setKod(String(navrh.kod))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navrh])

  if (nacitamZpevnik) return <LoadingState label="Načítám zpěvník…" />
  if (chybaZpevnik) {
    return (
      <ErrorState
        message={chybaZpevnik.status === 404 ? 'Tenhle zpěvník neexistuje.' : 'Zpěvník se nepodařilo načíst.'}
      />
    )
  }

  async function zalozit(e) {
    e.preventDefault()
    if (!nazev.trim() || !kod) return
    setZaklada(true)
    setChyba(null)
    try {
      const pisen = await api.post('/api/pisne/', { nazev: nazev.trim(), interpret: interpret.trim() })
      await api.post(`/api/zpevniky/${zpevnikId}/pridat-pisen/`, {
        pisen: pisen.id,
        kod: Number(kod),
      })
      const verze = await api.post(`/api/pisne/${pisen.id}/verze-akordy/`)
      navigate(`/verze-pisni/${verze.id}/akordy`, { replace: true })
    } catch (err) {
      setChyba(extractErrorMessage(err, CHYBA))
      setZaklada(false)
    }
  }

  return (
    <div className="nova-pisen-akordy-page">
      <Link to={`/zpevniky/${zpevnikId}`} className="breadcrumb-back">
        ← Zpět do zpěvníku
      </Link>

      <h1 className="section-heading">Nová píseň z akordů{zpevnik ? ` — ${zpevnik.nazev}` : ''}</h1>

      <form onSubmit={zalozit} className="nova-pisen-akordy-form">
        <div>
          <label className="field-label" htmlFor="np-nazev">
            Název
          </label>
          <input
            id="np-nazev"
            type="text"
            className="field-input"
            value={nazev}
            onChange={(e) => setNazev(e.target.value)}
            required
            autoFocus
          />
        </div>
        <div>
          <label className="field-label" htmlFor="np-interpret">
            Interpret
          </label>
          <input
            id="np-interpret"
            type="text"
            className="field-input"
            value={interpret}
            onChange={(e) => setInterpret(e.target.value)}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="np-kod">
            Kód ve zpěvníku
          </label>
          <input
            id="np-kod"
            type="number"
            className="field-input nova-pisen-akordy-kod"
            min={1}
            value={kod}
            onChange={(e) => setKod(e.target.value)}
            required
          />
        </div>

        {chyba && (
          <p className="akordy-editor-chyba" role="alert">
            {chyba}
          </p>
        )}

        <button type="submit" className="btn btn-primary" disabled={zaklada}>
          {zaklada ? 'Zakládám…' : 'Založit a otevřít editor'}
        </button>
      </form>
    </div>
  )
}
