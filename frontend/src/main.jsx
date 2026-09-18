import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

// Self-hostované fonty (žádné externí CDN) — jen váhy, které tokeny.css používá,
// a jen podsady latin/latin-ext (čeština je pokrytá, cyrillic/vietnamese ne potřebujeme).
import '@fontsource/oswald/latin-500.css'
import '@fontsource/oswald/latin-ext-500.css'
import '@fontsource/oswald/latin-600.css'
import '@fontsource/oswald/latin-ext-600.css'
import '@fontsource/oswald/latin-700.css'
import '@fontsource/oswald/latin-ext-700.css'
import '@fontsource/work-sans/latin-400.css'
import '@fontsource/work-sans/latin-ext-400.css'
import '@fontsource/work-sans/latin-500.css'
import '@fontsource/work-sans/latin-ext-500.css'
import '@fontsource/work-sans/latin-600.css'
import '@fontsource/work-sans/latin-ext-600.css'
import '@fontsource/work-sans/latin-700.css'
import '@fontsource/work-sans/latin-ext-700.css'
// Monospace pro akordy/taby v anotacích — musí být PEVNĚ tenhle font, ne
// systémový monospace stack. Ten se liší platforma od platformy (Menlo na
// iOS, Consolas na Windows) a s ním i šířka znaku, takže by se stejná
// zlomková šířka pole na iPadu a PC vizuálně jinak "naplnila" textem.
import '@fontsource/jetbrains-mono/latin-400.css'
import '@fontsource/jetbrains-mono/latin-ext-400.css'
import '@fontsource/jetbrains-mono/latin-700.css'
import '@fontsource/jetbrains-mono/latin-ext-700.css'

import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
