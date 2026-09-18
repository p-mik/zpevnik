import './ZpevnikVolba.css'

// Píseň je ve víc zpěvnících a žádný z nich nebyl použitý naposled v týhle
// relaci (viz useZpevnikKontext) — bez volby by čtečka nevěděla, čí kód a
// pořadí Předchozí/Další ukázat. `variant` přepíná paletu stejně jako
// AnnotationLayer ('app' čtečka vs. 'stage' pódium).
export default function ZpevnikVolba({ title, volby, onZvolit, variant = 'app' }) {
  return (
    <div className={`zpevnik-volba zpevnik-volba-${variant}`}>
      <h2>{title}</h2>
      <p>Píseň je ve víc zpěvnících — ve kterém ji chceš otevřít?</p>
      <ul className="zpevnik-volba-list">
        {volby.map((z) => (
          <li key={z.id}>
            <button type="button" className="zpevnik-volba-btn" onClick={() => onZvolit(z.zpevnik)}>
              <span className="code-chip">{String(z.kod).padStart(3, '0')}</span>
              <span className="zpevnik-volba-nazev">{z.zpevnik_nazev}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
