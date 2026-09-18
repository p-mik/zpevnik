import { useState } from 'react'
import PageThumbnail from './PageThumbnail'
import PagePreviewModal from './PagePreviewModal'
import { navrhniBezneJmeno } from './headerParser'
import '../components/ui.css'
import './ImportReviewTable.css'

const PROBLEM_LABELS = {
  'duplicitni-kod-import': 'Duplicitní kód (import)',
  'duplicitni-kod-db': 'Duplicitní kód (databáze)',
  'chybi-interpret': 'Chybí interpret',
  'bez-hlavicky': 'Bez hlavičky',
  'orphan-continuation': 'Pokračování bez předchozí písně',
}

const BLOCKING_TYPES = new Set(['duplicitni-kod-import', 'duplicitni-kod-db', 'orphan-continuation'])

export default function ImportReviewTable({ pdfDoc, pages, problems, updatePage, resolvedKodInfoByPage }) {
  const [vybrane, setVybrane] = useState(() => new Set())
  const [nahledStrana, setNahledStrana] = useState(null)

  function prepniVyber(pageNumber) {
    setVybrane((prev) => {
      const next = new Set(prev)
      if (next.has(pageNumber)) next.delete(pageNumber)
      else next.add(pageNumber)
      return next
    })
  }

  function prepniVsechny() {
    setVybrane((prev) => (prev.size === pages.length ? new Set() : new Set(pages.map((p) => p.page))))
  }

  function hromadne(patchNeboFn) {
    for (const pageNumber of vybrane) {
      const page = pages.find((p) => p.page === pageNumber)
      if (!page) continue
      updatePage(pageNumber, typeof patchNeboFn === 'function' ? patchNeboFn(page) : patchNeboFn)
    }
  }

  function prohodNazevInterpret(page) {
    updatePage(page.page, { nazev: page.interpret, interpret: page.nazev })
  }

  return (
    <div>
      {vybrane.size > 0 && (
        <div className="import-bulk-bar panel">
          <span className="import-bulk-count">Vybráno {vybrane.size} stran</span>
          <button type="button" className="btn" onClick={() => hromadne({ action: 'continuation' })}>
            Označit jako pokračování
          </button>
          <button type="button" className="btn" onClick={() => hromadne({ action: 'discard' })}>
            Vyřadit
          </button>
          <button
            type="button"
            className="btn"
            onClick={() =>
              hromadne((page) =>
                page.action === 'new' ? { nazev: page.interpret, interpret: page.nazev } : {},
              )
            }
            title="Prohodí název a interpret u vybraných řádků, které jsou nová píseň"
          >
            Prohodit název ↔ interpret
          </button>
          <button type="button" className="btn" onClick={() => setVybrane(new Set())}>
            Zrušit výběr
          </button>
        </div>
      )}

      <div className="import-table-wrap">
        <table className="import-table">
          <thead>
            <tr>
              <th className="import-col-vyber">
                <input
                  type="checkbox"
                  checked={vybrane.size > 0 && vybrane.size === pages.length}
                  onChange={prepniVsechny}
                  aria-label="Vybrat všechny strany"
                />
              </th>
              <th>Strana</th>
              <th>Náhled</th>
              <th>Kód</th>
              <th>Název</th>
              <th aria-hidden="true" />
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
                resolvedKod={resolvedKodInfoByPage?.get(page.page)}
                vybrano={vybrane.has(page.page)}
                onPrepniVyber={() => prepniVyber(page.page)}
                onProhodit={() => prohodNazevInterpret(page)}
                onOtevritNahled={() => setNahledStrana(page.page)}
              />
            ))}
          </tbody>
        </table>
      </div>

      {nahledStrana != null && (
        <PagePreviewModal
          pdfDoc={pdfDoc}
          pageNumber={nahledStrana}
          numPages={pages.length}
          onClose={() => setNahledStrana(null)}
          onNavigate={(delta) =>
            setNahledStrana((p) => Math.min(pages.length, Math.max(1, p + delta)))
          }
        />
      )}
    </div>
  )
}

function ImportTableRow({
  pdfDoc,
  page,
  rowProblems,
  updatePage,
  resolvedKod,
  vybrano,
  onPrepniVyber,
  onProhodit,
  onOtevritNahled,
}) {
  const isNew = page.action === 'new'
  const isDiscard = page.action === 'discard'
  // "Odhad" = parser tuhle stranu vyhodnotil jako pokračování a uživatel to
  // od té doby nezměnil (viz parsePdfPages.js) — badge zmizí, jakmile na
  // řádku někdo sáhne na Akci, i kdyby se pak vrátil na stejnou hodnotu.
  const jeOdhadPokracovani = page.action === 'continuation' && page.parsovanaAkce === 'continuation'

  const kodHodnota = page.kod ?? resolvedKod?.kod ?? ''
  const kodJeOdhad = page.kod == null && Boolean(resolvedKod?.odhad)

  return (
    <tr className={`import-row import-row-${page.action}`}>
      <td className="import-col-vyber">
        <input type="checkbox" checked={vybrano} onChange={onPrepniVyber} aria-label={`Vybrat stranu ${page.page}`} />
      </td>
      <td className="import-col-page">{page.page}</td>
      <td className="import-col-thumb">
        <PageThumbnail pdfDoc={pdfDoc} pageNumber={page.page} onOpen={onOtevritNahled} />
      </td>
      <td className="import-col-kod">
        {isNew ? (
          <input
            type="number"
            className={`field-input import-input-kod${kodJeOdhad ? ' import-input-kod-odhad' : ''}`}
            value={kodHodnota}
            title={kodJeOdhad ? 'Návrh z „Kódy od“ — zapsáním se stane pevným' : undefined}
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
      <td className="import-col-swap">
        {isNew && (
          <button
            type="button"
            className="import-swap-btn"
            onClick={onProhodit}
            title="Prohodit název a interpret"
            aria-label="Prohodit název a interpret"
          >
            ↔
          </button>
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
        {jeOdhadPokracovani && (
          <span className="import-odhad-badge" title="Parser odhadl pokračování — na stránce nenašel odlišnou hlavičku">
            odhad
          </span>
        )}
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
