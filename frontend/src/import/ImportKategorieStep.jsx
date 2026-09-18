import '../components/ui.css'
import './ImportKategorieStep.css'

export default function ImportKategorieStep({ kategorie, updateKategorie }) {
  if (kategorie.length === 0) {
    return <p className="import-kategorie-empty">Žádné kódy, ze kterých by šlo kategorie odvodit.</p>
  }

  return (
    <ul className="import-kategorie-list">
      {kategorie.map((k) => (
        <li key={k.digit} className="import-kategorie-row">
          <label className="import-kategorie-checkbox">
            <input
              type="checkbox"
              checked={k.vytvorit}
              onChange={(e) => updateKategorie(k.digit, { vytvorit: e.target.checked })}
            />
            <span className="code-chip import-kategorie-digit">{k.digit}xx</span>
          </label>
          <input
            type="text"
            className="field-input import-kategorie-nazev"
            value={k.nazev}
            disabled={!k.vytvorit}
            onChange={(e) => updateKategorie(k.digit, { nazev: e.target.value })}
          />
          <span className="import-kategorie-pocet">{k.pocet} písní</span>
        </li>
      ))}
    </ul>
  )
}
