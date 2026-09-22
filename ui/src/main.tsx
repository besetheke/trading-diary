import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import PositionDetail from './PositionDetail'
import Positionen from './Positionen'
import './stil.css'

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
        </header>
        <main>
          <Routes>
            <Route path="/" element={<Positionen />} />
            <Route path="/positionen/:chainId" element={<PositionDetail />} />
            <Route path="*" element={<Unbekannt />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  </React.StrictMode>,
)
