import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import Dashboard from './Dashboard'
import Kalender from './Kalender'
import Kampagnen from './Kampagnen'
import PositionDetail from './PositionDetail'
import Positionen from './Positionen'
import Tag from './Tag'
import './stil.css'

// AP-08j: „Heute" zeigt das Datum der lokalen Zeit des Browsers — kein
// toISOString, das je Zeitzone auf den Vortag rutschen würde.
function heuteDatum(): string {
  const jetzt = new Date()
  const monat = String(jetzt.getMonth() + 1).padStart(2, '0')
  const tag = String(jetzt.getDate()).padStart(2, '0')
  return `${jetzt.getFullYear()}-${monat}-${tag}`
}

function Unbekannt(): JSX.Element {
  return (
    <section className="hinweis">
      <p>Diese Adresse gehört zu keiner Ansicht.</p>
      <p>
        <Link to="/">Zur Positionsliste</Link>
      </p>
    </section>
  )
}

ReactDOM.createRoot(document.getElementById('wurzel') as HTMLElement).render(
  <React.StrictMode>
    <BrowserRouter>
      <div className="geruest">
        <header>
          <h1>
            <Link to="/">Trading Journal</Link>
          </h1>
          <p className="sicht">
            Alle Geldbeträge in Kontosicht — die Kettensicht ist noch nicht gebaut.
            Beträge bleiben unverändert, wie die API sie liefert.
          </p>
          <nav className="hauptnav">
            <Link to="/">Positionen</Link>
            <Link to="/dashboard">Dashboard</Link>
            <Link to="/kampagnenliste">Kampagnen</Link>
            <Link to="/monat">Kalender</Link>
            <Link to={`/tag/${heuteDatum()}`}>Heute</Link>
          </nav>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<Positionen />} />
            {/* AP-06e: eigene Adresse, kollidiert mit keinem API-Pfad
                (anders als /kalender, /kampagnen — /equity bleibt API). */}
            <Route path="/dashboard" element={<Dashboard />} />
            {/* AP-08j2: /kalender ist der API-Endpunkt (AP-07t). Die Seite
                heißt /monat, damit Neuladen und Lesezeichen die Oberfläche
                erreichen und nicht den JSON-Fehler 422 des Endpunkts. */}
            <Route path="/monat" element={<Kalender />} />
            {/* AP-08-kampagnen: ebenso heißt die Seite /kampagnenliste —
                /kampagnen und /kampagnen/{id} sind API-Endpunkte. */}
            <Route path="/kampagnenliste" element={<Kampagnen />} />
            <Route path="/positionen/:chainId" element={<PositionDetail />} />
            <Route path="/tag/:datum" element={<Tag />} />
            <Route path="*" element={<Unbekannt />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  </React.StrictMode>,
)
