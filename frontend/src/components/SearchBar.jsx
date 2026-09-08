import './ui.css'
import './SearchBar.css'

// Jedno pole na obě cesty ze zadání: čistě číselný vstup = kód (přesná
// shoda, používá se při hraní), cokoliv jiného = hledání v názvu/interpretovi.
export default function SearchBar({ value, onChange, placeholder = 'Kód nebo název…' }) {
  return (
    <div className="search-bar">
      <input
        className="field-input"
        type="text"
        inputMode="search"
        autoComplete="off"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        aria-label="Hledat píseň podle kódu nebo názvu"
      />
    </div>
  )
}

export function parseSearchQuery(raw) {
  const trimmed = raw.trim()
  if (trimmed === '') return {}
  if (/^\d+$/.test(trimmed)) return { kod: trimmed }
  return { search: trimmed }
}
