import PageThumbnail from './PageThumbnail'
import { navrhniBezneJmeno } from './headerParser'
import '../components/ui.css'
import './ImportReviewTable.css'

const PROBLEM_LABELS = {
  'chybi-kod': 'Chybí kód',
  'duplicitni-kod-import': 'Duplicitní kód (import)',
  'duplicitni-kod-db': 'Duplicitní kód (databáze)',
  'chybi-interpret': 'Chybí interpret',
  'bez-hlavicky': 'Bez hlavičky',
  'orphan-continuation': 'Pokračování bez předchozí písně',
}

const BLOCKING_TYPES = new Set([
  'chybi-kod',
  'duplicitni-kod-import',
  'duplicitni-kod-db',
  'orphan-continuation',
])

export default function ImportReviewTable({ pdfDoc, pages, problems, updatePage }) {
  return (
    <div className="import-table-wrap">
      <table className="import-table">
        <thead>
          <tr>
            <th>Strana</th>
            <th>Náhled</th>
            <th>Kód</th>
            <th>Název</th>
            <th>Interpret</th>
            <th>Akce</th>
          </tr>
        </thead>
        <tbody>
          {pages.map((page) => (
            <ImportTableRow
              key={page.page}
              pdfDoc={pdfDoc}
              page={page}
              rowProblems={problems.get(page.page) || []}
              updatePage={updatePage}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ImportTableRow({ pdfDoc, page, rowProblems, updatePage }) {
  const isNew = page.action === 'new'
  const isDiscard = page.action === 'discard'

  return (
    <tr className={`import-row import-row-${page.action}`}>
      <td className="import-col-page">{page.page}</td>
      <td className="import-col-thumb">
        <PageThumbnail pdfDoc={pdfDoc} pageNumber={page.page} />
      </td>
      <td className="import-col-kod">
        {isNew ? (
          <input
            type="number"
            className="field-input import-input-kod"
            value={page.kod ?? ''}
            onChange={(e) =>
              updatePage(page.page, {
                kod: e.target.value === '' ? null : Number(e.target.value),
              })
            }
            placeholder="kód"
          />
        ) : (
          <InheritedHint page={page} isDiscard={isDiscard} />
        )}
      </td>
      <td className="import-col-nazev">
        {isNew ? (
          <div className="import-nazev-cell">
            <input
              type="text"
              className="field-input"
              value={page.nazev}
              onChange={(e) => updatePage(page.page, { nazev: e.target.value })}
              placeholder="název"
            />
            <button
              type="button"
              className="import-suggest-btn"
              title="Navrhnout běžné psaní místo VERZÁLEK"
              onClick={() => updatePage(page.page, { nazev: navrhniBezneJmeno(page.nazev) })}
            >
              Aa
            </button>
          </div>
        ) : (
          !isDiscard && <span className="import-muted">{page.nazev}</span>
        )}
      </td>
      <td className="import-col-interpret">
        {isNew ? (
          <input
            type="text"
            className="field-input"
            value={page.interpret}
            onChange={(e) => updatePage(page.page, { interpret: e.target.value })}
            placeholder="(bez interpreta)"
          />
        ) : (
          !isDiscard && <span className="import-muted">{page.interpret}</span>
        )}
      </td>
      <td className="import-col-akce">
        <select
          className="import-action-select"
          value={page.action}
          onChange={(e) => updatePage(page.page, { action: e.target.value })}
        >
          <option value="new">Nová píseň</option>
          <option value="continuation">Pokračování předchozí</option>
          <option value="discard">Vyřadit</option>
        </select>
        {rowProblems.length > 0 && (
          <div className="import-problems">
            {rowProblems.map((p, i) => (
              <span
                key={i}
                className={`problem-badge ${BLOCKING_TYPES.has(p.type) ? 'problem-badge-error' : 'problem-badge-warning'}`}
              >
                {PROBLEM_LABELS[p.type] || p.type}
              </span>
            ))}
          </div>
        )}
      </td>
    </tr>
  )
}

function InheritedHint({ page, isDiscard }) {
  if (isDiscard) return <span className="import-muted import-discarded">vyřazeno</span>
  return <span className="import-muted">↳ pokrač.</span>
}
