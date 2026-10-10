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
      // AP-08j2: Lese- und Journal-Wege der API (AP-07t, AP-07jk). Der
      // Proxy greift nur für Anfragen mit diesen Anfängen — die Kalender-
      // Seite heißt deshalb /monat und bleibt beim Entwicklungsserver.
      '/tage': 'http://localhost:8000',
      '/kalender': 'http://localhost:8000',
      '/journal': 'http://localhost:8000',
      '/tags': 'http://localhost:8000',
      // AP-08-kampagnen: die Kampagnen-Endpunkte; die Seite heißt
      // /kampagnenliste und bleibt beim Entwicklungsserver.
      '/kampagnen': 'http://localhost:8000',
      // AP-06e: die Equity-Kurve; die Seite heißt /dashboard, keine
      // Kollision möglich.
      '/equity': 'http://localhost:8000',
      // AP-06f/AP-06g: Kosten & Erträge und Kapital.
      '/cashflows': 'http://localhost:8000',
      '/kapital': 'http://localhost:8000',
    },
  },
})
