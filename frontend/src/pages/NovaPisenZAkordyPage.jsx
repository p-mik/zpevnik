import { useEffect, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { useApiResource } from '../hooks/useApiResource'
import { useAllPages } from '../hooks/useAllPages'
import { api } from '../api/client'
import { extractErrorMessage } from '../api/errors'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import '../components/ui.css'
import './NovaPisenZAkordyPage.css'

const CHYBA = 'Píseň se nepodařilo založit.'

// Stejný sessionStorage klíč jako čtečka (viz pdf/useZpevnikKontext.js) —
// "poslední použitý zpěvník" je jeden sdílený pojem napříč appkou, jen se
// nedotýkáme toho souboru samotného (zákaz, viz PC_zpevnik_sprava.md).
const KLIC_POSLEDNI_ZPEVNIK = 'zpevnik:posledni-zpevnik'

function nactiPosledniZpevnik() {
  try {
    return sessionStorage.getItem(KLIC_POSLEDNI_ZPEVNIK)
  } catch {
    return null
  }
}

function ulozPosledniZpevnik(id) {
  try {
    sessionStorage.setItem(KLIC_POSLEDNI_ZPEVNIK, String(id))
  } catch {
    // soukromý režim / zakázané úložiště — appka na to nespoléhá jako na nutnost
  }
}

// "Nová píseň z akordů" — buď ze stránky KONKRÉTNÍHO zpěvníku
// (/zpevniky/:zpevnikId/nova-pisen-akordy, zpěvník je daný), nebo z
// globálního seznamu písní (/pisne/nova-pisen-akordy — bez :zpevnikId), kde
// formulář navíc nabídne výběr zpěvníku (povinný, píseň vždy patří do
// nějakého) předvyplněný posledním použitým z sessionStorage.
//
// Založí píseň, zařadí ji do zvoleného zpěvníku pod zadaným kódem a rovnou
// otevře editor prázdné akordové verze. Tři API volání za sebou (píseň →
// zařazení → verze) nejsou v jedné transakci: při kolizi kódu (vzácné,
// návrh z dalsi-kod je čerstvý) píseň už existuje, jen bez zařazení — dá se
// dohotovit později, appka to nezkouší tiše řešit rollbackem.
export default function NovaPisenZAkordyPage() {
  const { zpevnikId: zpevnikIdZParametru } = useParams()
  const navigate = useNavigate()

  const [vybranyZpevnikId, setVybranyZpevnikId] = useState(zpevnikIdZParametru || '')

  const { data: seznamZpevniku, loading: nacitamSeznam } = useAllPages(
    zpevnikIdZParametru ? null : '/api/zpevniky/',
  )

  useEffect(() => {
    if (zpevnikIdZParametru || !seznamZpevniku || vybranyZpevnikId) return
    const posledni = nactiPosledniZpevnik()
    const platny = posledni && seznamZpevniku.some((z) => String(z.id) === posledni)
    if (platny) setVybranyZpevnikId(posledni)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seznamZpevniku])

  const { data: zpevnik, loading: nacitamZpevnik, error: chybaZpevnik } = useApiResource(
    zpevnikIdZParametru ? `/api/zpevniky/${zpevnikIdZParametru}/` : null,
  )
  const { data: navrh } = useApiResource(
    vybranyZpevnikId ? `/api/zpevniky/${vybranyZpevnikId}/dalsi-kod/` : null,
  )

  const [nazev, setNazev] = useState('')
  const [interpret, setInterpret] = useState('')
  const [kod, setKod] = useState('')
  const [zaklada, setZaklada] = useState(false)
  const [chyba, setChyba] = useState(null)

  useEffect(() => {
    setKod(navrh?.kod != null ? String(navrh.kod) : '')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [navrh, vybranyZpevnikId])

  if (zpevnikIdZParametru && nacitamZpevnik) return <LoadingState label="Načítám zpěvník…" />
  if (chybaZpevnik) {
    return (
      <ErrorState
        message={chybaZpevnik.status === 404 ? 'Tenhle zpěvník neexistuje.' : 'Zpěvník se nepodařilo načíst.'}
      />
    )
  }
  if (!zpevnikIdZParametru && nacitamSeznam) return <LoadingState label="Načítám zpěvníky…" />

  function zmenVyberZpevniku(id) {
    setVybranyZpevnikId(id)
    if (id) ulozPosledniZpevnik(id)
  }

  async function zalozit(e) {
    e.preventDefault()
    if (!nazev.trim() || !kod || !vybranyZpevnikId) return
    setZaklada(true)
    setChyba(null)
    try {
      const pisen = await api.post('/api/pisne/', { nazev: nazev.trim(), interpret: interpret.trim() })
      await api.post(`/api/zpevniky/${vybranyZpevnikId}/pridat-pisen/`, {
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
      <Link to={zpevnikIdZParametru ? `/zpevniky/${zpevnikIdZParametru}` : '/pisne'} className="breadcrumb-back">
        {zpevnikIdZParametru ? '← Zpět do zpěvníku' : '← Zpět na seznam písní'}
      </Link>

      <h1 className="section-heading">Nová píseň z akordů{zpevnik ? ` — ${zpevnik.nazev}` : ''}</h1>

      <form onSubmit={zalozit} className="nova-pisen-akordy-form">
        {!zpevnikIdZParametru && (
          <div>
            <label className="field-label" htmlFor="np-zpevnik">
              Zpěvník
            </label>
            <select
              id="np-zpevnik"
              className="field-input"
              value={vybranyZpevnikId}
              onChange={(e) => zmenVyberZpevniku(e.target.value)}
              required
            >
              <option value="" disabled>
                Vyber zpěvník…
              </option>
              {(seznamZpevniku || []).map((z) => (
                <option key={z.id} value={z.id}>
                  {z.nazev}
                </option>
              ))}
            </select>
          </div>
        )}
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
            autoFocus={Boolean(zpevnikIdZParametru)}
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

        <button type="submit" className="btn btn-primary" disabled={zaklada || !vybranyZpevnikId}>
          {zaklada ? 'Zakládám…' : 'Založit a otevřít editor'}
        </button>
      </form>
    </div>
  )
}
