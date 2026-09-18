import { useRef } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
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

function ImportWizard() {
  const wizard = useImportWizard()
  const fileInputRef = useRef(null)

  return (
    <div className="import-page">
      <h1>Hromadný import zpěvníku</h1>
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
          <h2 className="section-heading">Celý zpěvník</h2>
          <p className="import-intro">
            Jeden zpěvník se všemi {wizard.songs.length} písněmi — na tenhle má smysl navázat
            setlist nebo mu později v adminu vygenerovat jeden veřejný QR odkaz. Nezávisí na
            kategoriích níž, píseň může být v obou zároveň.
          </p>
          <div className="import-cely-zpevnik panel">
            <label className="import-kategorie-checkbox">
              <input
                type="checkbox"
                checked={wizard.celyZpevnik.vytvorit}
                onChange={(e) => wizard.updateCelyZpevnik({ vytvorit: e.target.checked })}
              />
            </label>
            <input
              type="text"
              className="field-input import-cely-zpevnik-nazev"
              value={wizard.celyZpevnik.nazev}
              disabled={!wizard.celyZpevnik.vytvorit}
              onChange={(e) => wizard.updateCelyZpevnik({ nazev: e.target.value })}
            />
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
            <button type="button" className="btn btn-primary" onClick={wizard.submit}>
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
  return (
    <div className="import-summary panel">
      <span>
        <strong>{wizard.pages.length}</strong> stran, <strong>{rozpoznano}</strong> s
        rozpoznanou hlavičkou, <strong>{wizard.songs.length}</strong> písní k založení
      </span>
      {wizard.pocetProblemu > 0 && (
        <span className="import-summary-problems">{wizard.pocetProblemu} věcí k pohledu</span>
      )}
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
