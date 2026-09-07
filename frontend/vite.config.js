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
}))
