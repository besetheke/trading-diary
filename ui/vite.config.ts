import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Vertrag 13: In der Entwicklung dient der Vite-Server und leitet die
// API-Wege an localhost:8000 weiter; im Betrieb wird gebaut (`npm run build`)
// und die API liefert ui/dist statisch aus (api/app.py, AP-08l).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/ketten': 'http://localhost:8000',
      '/strukturen': 'http://localhost:8000',
      '/openapi.json': 'http://localhost:8000',
    },
  },
})
