import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import Kalender from './Kalender'
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
            <Link to="/kalender">Kalender</Link>
            <Link to={`/tag/${heuteDatum()}`}>Heute</Link>
          </nav>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<Positionen />} />
            <Route path="/kalender" element={<Kalender />} />
            <Route path="/positionen/:chainId" element={<PositionDetail />} />
            <Route path="/tag/:datum" element={<Tag />} />
            <Route path="*" element={<Unbekannt />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  </React.StrictMode>,
)
