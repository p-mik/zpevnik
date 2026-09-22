import { useRef } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useApiResource } from '../hooks/useApiResource'
import { useImportWizard } from '../import/useImportWizard'
import ImportReviewTable from '../import/ImportReviewTable'
import ImportKategorieStep from '../import/ImportKategorieStep'
import LoadingState from '../components/LoadingState'
import ErrorState from '../components/ErrorState'
import '../components/ui.css'
import '../import/ImportKategorieStep.css'
import './ImportPage.css'

export default function ImportPage() {
  const { user } = useAuth()

  if (user?.role !== 'admin') {
    return <ErrorState message="Hromadný import je jen pro adminy." />
  }

  return <ImportWizard />
}

// ?zpevnik=<id> — import spuštěný z konkrétního zpěvníku (viz SongbookPage
// "+ Import PDF") předvyplní cíl, ať ho uživatel nemusí hledat ve výběru.
function ImportWizard() {
  const [searchParams] = useSearchParams()
  const presetZpevnikId = searchParams.get('zpevnik')
  const { data: presetZpevnik } = useApiResource(
    presetZpevnikId ? `/api/zpevniky/${presetZpevnikId}/` : null,
  )
  const wizard = useImportWizard(presetZpevnikId)
  const fileInputRef = useRef(null)

  return (
    <div className="import-page">
      <h1>Hromadný import zpěvníku{presetZpevnik ? ` — ${presetZpevnik.nazev}` : ''}</h1>
      <p className="import-intro">
        Nahraj jedno PDF s celým zpěvníkem — parser navrhne rozdělení na jednotlivé písně,
        ty pak potvrdíš (nebo opravíš) v tabulce. Nic se nezaloží, dokud to na konci
        nepotvrdíš.
      </p>

      {wizard.step === 'upload' && (
        <div className="import-upload panel">
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf"
            onChange={(e) => wizard.selectFile(e.target.files?.[0])}
            className="import-file-input"
          />
          {wizard.parseError && (
            <p className="import-parse-error" role="alert">
              {wizard.parseError}
            </p>
          )}
        </div>
      )}

      {wizard.step === 'parsing' && (
        <LoadingState
          label={
            wizard.parseProgress.total
              ? `Čtu stránku ${wizard.parseProgress.done} z ${wizard.parseProgress.total}…`
              : 'Otevírám PDF…'
          }
        />
      )}

      {wizard.step === 'review' && (
        <>
          <ImportSummaryBar wizard={wizard} />
          <ImportReviewTable
            pdfDoc={wizard.pdfDoc}
            pages={wizard.pages}
            problems={wizard.problems}
            updatePage={wizard.updatePage}
            resolvedKodInfoByPage={wizard.resolvedKodInfoByPage}
          />
          <div className="import-actions">
            <button type="button" className="btn" onClick={wizard.zacitZnovu}>
              Začít znovu
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={!wizard.jeValidni}
              onClick={wizard.goToKategorie}
            >
              Pokračovat na kategorie ({wizard.songs.length} písní)
            </button>
          </div>
        </>
      )}

      {wizard.step === 'kategorie' && (
        <>
          <h2 className="section-heading">Cíl importu</h2>
          <p className="import-intro">
            Zpěvník, do kterého se zařadí všech {wizard.songs.length} písní — existující, nebo
            nový. Kód z tabulky se použije, pokud je v cílovém zpěvníku volný; při kolizi píseň
            dostane další volný kód (uvidíš v souhrnu po dokončení). Nezávisí na kategoriích níž,
            píseň může být v obou zároveň.
          </p>
          <div className="import-cely-zpevnik panel">
            <div className="import-cily-volba">
              <label>
                <input
                  type="radio"
                  name="cily-zpevnik-mod"
                  checked={wizard.celyZpevnik.mod === 'novy'}
                  onChange={() => wizard.updateCelyZpevnik({ mod: 'novy' })}
                />
                Nový zpěvník
              </label>
              <label>
                <input
                  type="radio"
                  name="cily-zpevnik-mod"
                  checked={wizard.celyZpevnik.mod === 'existujici'}
                  onChange={() => wizard.updateCelyZpevnik({ mod: 'existujici' })}
                />
                Existující zpěvník
              </label>
            </div>

            {wizard.celyZpevnik.mod === 'novy' ? (
              <input
                type="text"
                className="field-input import-cely-zpevnik-nazev"
                placeholder="Název nového zpěvníku"
                value={wizard.celyZpevnik.nazev}
                onChange={(e) => wizard.updateCelyZpevnik({ nazev: e.target.value })}
                required
              />
            ) : (
              <select
                className="field-input import-cely-zpevnik-nazev"
                value={wizard.celyZpevnik.existujiciId}
                onChange={(e) => wizard.updateCelyZpevnik({ existujiciId: e.target.value })}
                required
              >
                <option value="" disabled>
                  Vyber zpěvník…
                </option>
                {wizard.vsechnyZpevniky.map((z) => (
                  <option key={z.id} value={z.id}>
                    {z.nazev}
                  </option>
                ))}
              </select>
            )}
            {!wizard.celyZpevnikValidni && (
              <p className="import-cily-chyba">
                {wizard.celyZpevnik.mod === 'novy' ? 'Zadej název nového zpěvníku.' : 'Vyber cílový zpěvník.'}
              </p>
            )}
          </div>

          <h2 className="section-heading">Kategorie ze složek</h2>
          <p className="import-intro">
            Volitelné rozdělení pro procházení podle první číslice kódu. Název jde
            přejmenovat, kategorii jde odškrtnutím přeskočit úplně.
          </p>
          <ImportKategorieStep kategorie={wizard.kategorie} updateKategorie={wizard.updateKategorie} />
          {wizard.submitError && (
            <div className="toast-error import-submit-error" role="alert">
              {wizard.submitError}
            </div>
          )}
          <div className="import-actions">
            <button type="button" className="btn" onClick={wizard.goToReview}>
              Zpět na tabulku
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={wizard.submit}
              disabled={!wizard.celyZpevnikValidni}
            >
              Provést import ({wizard.songs.length} písní)
            </button>
          </div>
        </>
      )}

      {wizard.step === 'submitting' && <LoadingState label="Provádím import…" />}

      {wizard.step === 'result' && wizard.result?.ok && (
        <ImportResult data={wizard.result.data} onZnovu={wizard.zacitZnovu} />
      )}
    </div>
  )
}

function ImportSummaryBar({ wizard }) {
  const rozpoznano = wizard.pages.filter((p) => p.headerFound).length
  const pokracovani = wizard.pages.filter((p) => p.action === 'continuation').length
  const kodyOdhadem = wizard.songs.filter((s) => s.kodOdhad).length

  return (
    <div className="import-summary panel">
      <span>
        <strong>{wizard.pages.length}</strong> stran, <strong>{rozpoznano}</strong> s
        rozpoznanou hlavičkou, <strong>{pokracovani}</strong> jako pokračování,{' '}
        <strong>{wizard.songs.length}</strong> písní k založení
      </span>
      {wizard.pocetProblemu > 0 && (
        <span className="import-summary-problems">{wizard.pocetProblemu} věcí k pohledu</span>
      )}
      <label className="import-kody-od">
        Kódy od:
        <input
          type="number"
          className="field-input import-kody-od-input"
          value={wizard.kodyOdText}
          onChange={(e) => wizard.setKodyOdText(e.target.value)}
          placeholder={String(wizard.vychoziKodyOd)}
        />
        {kodyOdhadem > 0 && (
          <span className="import-kody-od-hint">
            {kodyOdhadem} {kodyOdhadem === 1 ? 'píseň dostane' : 'písní dostane'} dopočítaný kód
          </span>
        )}
      </label>
    </div>
  )
}

function ImportResult({ data, onZnovu }) {
  return (
    <div className="import-result panel">
      <h2>Hotovo</h2>
      <p>
        Založeno <strong>{data.pisne.length}</strong> písní
        {data.zpevniky.length > 0 && (
          <>
            {' '}
            do {data.zpevniky.length} {data.zpevniky.length === 1 ? 'zpěvníku' : 'zpěvníků'} (
            {data.zpevniky.join(', ')})
          </>
        )}
        .
      </p>
      {data.prejmenovani_kodu?.length > 0 && (
        <div className="import-prejmenovani">
          <p>
            {data.prejmenovani_kodu.length}{' '}
            {data.prejmenovani_kodu.length === 1 ? 'píseň dostala' : 'písní dostalo'} v cílovém
            zpěvníku jiný kód, protože ten z PDF tam už byl obsazený:
          </p>
          <ul className="import-result-list">
            {data.prejmenovani_kodu.map((p) => (
              <li key={`${p.puvodni}-${p.novy}-${p.nazev}`}>
                <span className="code-chip">
                  {String(p.puvodni).padStart(3, '0')} → {String(p.novy).padStart(3, '0')}
                </span>
                <span>{p.nazev}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <ul className="import-result-list">
        {data.pisne.map((p) => (
          <li key={p.id}>
            <Link to={`/pisne/${p.id}`} className="code-chip">
              {String(p.kod).padStart(3, '0')}
            </Link>
            <span>{p.nazev}</span>
          </li>
        ))}
      </ul>
      <div className="import-actions">
        <button type="button" className="btn btn-primary" onClick={onZnovu}>
          Importovat další PDF
        </button>
        <Link to="/pisne" className="btn">
          Zpět na seznam písní
        </Link>
      </div>
    </div>
  )
}
