// Sdílené inline SVG ikony pro redesign editoru (docs/zadani_redesign_akordovy_zapis.md
// bod 5) — JEDEN partial, ať se cesty SVG nekopírují po komponentách (zadání to
// výslovně chce). Společný základ (viewBox 16x16, fill none, stroke currentColor,
// stroke-width 1.5, stroke-linecap square) nese `Zakladni`; pár ikon s jiným
// viewBoxem/rozměry (repetice, volta, takt) si kreslí vlastní <svg> obal.
//
// Šipky nahoru/dolů: zadání má v tabulce bodu 5 jen JEDNU dvojici cest
// (`M3 11l5-5 5 5` / `M3 5l5 5 5-5`). Referenční mockup pro řádek "Jen nadpis"
// používá jinou (nekonzistentní) variantu cesty — podle zadání je mockup jen
// předloha rozměrů/barev, ne zdroj pravdy pro tvary, takže se tu používá
// všude STEJNÁ dvojice z tabulky, jen v jiné velikosti/tloušťce čáry podle
// kontextu (viz props size/strokeWidth u volajících).

function Zakladni({ children, size = 16, strokeWidth = 1.5, className }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="square"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  )
}

export function IkonaZpet(props) {
  return (
    <Zakladni {...props}>
      <path d="M13 8H3M7 4L3 8l4 4" />
    </Zakladni>
  )
}

export function IkonaNahoru(props) {
  return (
    <Zakladni strokeWidth={2} {...props}>
      <path d="M3 11l5-5 5 5" />
    </Zakladni>
  )
}

export function IkonaDolu(props) {
  return (
    <Zakladni strokeWidth={2} {...props}>
      <path d="M3 5l5 5 5-5" />
    </Zakladni>
  )
}

export function IkonaSpojitSPredchozi(props) {
  return (
    <Zakladni {...props}>
      <path d="M3 2.5h10M8 14V6M5 9l3-3 3 3" />
    </Zakladni>
  )
}

export function IkonaDuplikovat({ size = 16, className }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <rect x="5" y="5" width="8.5" height="8.5" />
      <path d="M2.5 10.5V2.5h8" />
    </svg>
  )
}

export function IkonaSmazat(props) {
  return (
    <Zakladni {...props}>
      <path d="M3 4h10M6 4V2.5h4V4M4.5 4l.7 9.5h5.6l.7-9.5" />
    </Zakladni>
  )
}

export function IkonaNuzky({ size = 16, className }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.4}
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <circle cx="4" cy="4" r="2" />
      <circle cx="4" cy="12" r="2" />
      <path d="M5.6 5.2L14 12M5.6 10.8L14 4" />
    </svg>
  )
}

export function IkonaPridatSekci(props) {
  return (
    <Zakladni {...props}>
      <rect x="2" y="3" width="12" height="10" />
      <path d="M8 6v4M6 8h4" />
    </Zakladni>
  )
}

export function IkonaNadpis(props) {
  return (
    <Zakladni {...props}>
      <path d="M3 3h10M8 3v10" />
    </Zakladni>
  )
}

export function IkonaPlus(props) {
  return (
    <Zakladni strokeWidth={1.8} {...props}>
      <path d="M8 3v10M3 8h10" />
    </Zakladni>
  )
}

export function IkonaKrizek(props) {
  return (
    <Zakladni strokeWidth={2} {...props}>
      <path d="M4 4l8 8M12 4l-8 8" />
    </Zakladni>
  )
}

export function IkonaRepetice({ width = 20, height = 16, className }) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 20 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <path d="M2 2v12M4.5 2v12M15.5 2v12M18 2v12" />
      <circle cx="7.5" cy="6" r=".9" fill="currentColor" />
      <circle cx="7.5" cy="10" r=".9" fill="currentColor" />
      <circle cx="12.5" cy="6" r=".9" fill="currentColor" />
      <circle cx="12.5" cy="10" r=".9" fill="currentColor" />
    </svg>
  )
}

export function IkonaVolta({ size = 16, className }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="square"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <path d="M2 14V3h12" />
      <text x="4.5" y="11" fontSize="7" fontFamily="Oswald" fill="currentColor" stroke="none">
        1.
      </text>
    </svg>
  )
}

export function IkonaTakt({ size = 16, className }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.2}
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <text x="5" y="7" fontSize="7" fontFamily="Oswald" fill="currentColor" stroke="none">
        3
      </text>
      <text x="5" y="15" fontSize="7" fontFamily="Oswald" fill="currentColor" stroke="none">
        4
      </text>
      <path d="M3 8.5h10" />
    </svg>
  )
}
