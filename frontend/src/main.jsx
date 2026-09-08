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

import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
