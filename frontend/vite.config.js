import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => ({
  plugins: [react()],
  // V produkci Django/WhiteNoise servíruje z /static/frontend/
  base: mode === 'production' ? '/static/frontend/' : '/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    // `npm run dev` běží na vlastním portu — API a admin cookie (CSRF, session)
    // musí jít na skutečný Django backend v Dockeru, ne na Vite dev server.
    proxy: {
      '/api': 'http://localhost:8007',
    },
  },
}))
