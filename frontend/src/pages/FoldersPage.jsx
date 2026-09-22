import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useAllPages } from '../hooks/useAllPages'
import { useAuth } from '../auth/AuthContext'
import { api } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import EmptyState from '../components/EmptyState'
import '../components/ui.css'
import './FoldersPage.css'

export default function FoldersPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { user } = useAuth()
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

  const [formOtevreny, setFormOtevreny] = useState(false)

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

      <div className="folders-head">
        <h1 className="section-heading">{currentFolder ? currentFolder.nazev : 'Složky'}</h1>
        {user?.role === 'admin' && (
          <button type="button" className="btn btn-secondary" onClick={() => setFormOtevreny((v) => !v)}>
            + Nový zpěvník
          </button>
        )}
      </div>

      {formOtevreny && (
        <NovyZpevnikForm
          slozkaId={currentId}
          onZalozeno={(zpevnik) => navigate(`/zpevniky/${zpevnik.id}`)}
          onZrusit={() => setFormOtevreny(false)}
        />
      )}

      {isEmpty && !formOtevreny && (
        <EmptyState
          title="Tady zatím nic není"
          description={
            user?.role === 'admin'
              ? 'Založ nový zpěvník tlačítkem nahoře, nebo naimportuj PDF.'
              : 'Složky a zpěvníky zakládá admin.'
          }
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

const CHYBA_ZALOZENI = 'Zpěvník se nepodařilo založit.'

// Model Zpevnik nemá pole pro popis (viz zpevnik/models.py) — formulář má
// proto jen název (PC_zpevnik_sprava.md bod 2: "volitelný popis, pokud ho
// model má" — nemá). Nový zpěvník se chová stejně jako importovaný: žádné
// vlastnictví/skupina v modelu není, viditelnost řídí jen IsStaffOrReadOnly
// na ZpevnikViewSet (čtení každému přihlášenému, zápis adminovi) — přesně
// stejně jako u kteréhokoliv jiného zpěvníku.
function NovyZpevnikForm({ slozkaId, onZalozeno, onZrusit }) {
  const [nazev, setNazev] = useState('')
  const [zaklada, setZaklada] = useState(false)
  const [chyba, setChyba] = useState(null)

  async function zalozit(e) {
    e.preventDefault()
    if (!nazev.trim()) return
    setZaklada(true)
    setChyba(null)
    try {
      const zpevnik = await api.post('/api/zpevniky/', { nazev: nazev.trim(), slozka: slozkaId })
      onZalozeno(zpevnik)
    } catch (err) {
      setChyba(extractErrorMessage(err, CHYBA_ZALOZENI))
      setZaklada(false)
    }
  }

  return (
    <form onSubmit={zalozit} className="panel folders-novy-zpevnik-form">
      <div>
        <label className="field-label" htmlFor="nz-nazev">
          Název zpěvníku
        </label>
        <input
          id="nz-nazev"
          type="text"
          className="field-input"
          value={nazev}
          onChange={(e) => setNazev(e.target.value)}
          required
          autoFocus
        />
      </div>

      {chyba && (
        <p className="akordy-editor-chyba" role="alert">
          {chyba}
        </p>
      )}

      <div className="folders-novy-zpevnik-akce">
        <button type="submit" className="btn btn-primary" disabled={zaklada}>
          {zaklada ? 'Zakládám…' : 'Založit zpěvník'}
        </button>
        <button type="button" className="btn" onClick={onZrusit} disabled={zaklada}>
          Zrušit
        </button>
      </div>
    </form>
  )
}
