import { STAV_LABELS } from '../constants'
import './VersionSwitcher.css'

// Jen verze se souborem se dají otevřít — jinak by přepnutí skončilo
// chybou z API, aniž by to uživateli dávalo smysl.
export default function VersionSwitcher({ verze, currentId, onChange }) {
  const dostupne = verze.filter((v) => v.ma_soubor)
  if (dostupne.length < 2) return null

  return (
    <div className="version-switcher" role="group" aria-label="Verze písně">
      {dostupne.map((v) => (
        <button
          key={v.id}
          type="button"
          className={`version-chip${v.id === currentId ? ' version-chip-active' : ''}`}
          onClick={() => onChange(v.id)}
          aria-pressed={v.id === currentId}
        >
          {STAV_LABELS[v.stav] || v.stav}
        </button>
      ))}
    </div>
  )
}
