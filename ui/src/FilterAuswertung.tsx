import type { Auswertung } from './api'
import { datumDe } from './format'
import Betrag from './Betrag'
import Balken from './diagramm/Balken'
import Linie from './diagramm/Linie'

// AP-08g2b: Verlauf und Ergebnis der gefilterten Positionen (GET /auswertung,
// AP-07f). Alles kommt als Text aus der API und wird nur formatiert (D2,
// Vertrag 8): Summe, Drawdown und Kurve rechnet das Backend.
//
// Zeitraum: In der Positionsliste heißt „im Zeitraum" aktiv (Z3); die
// Auswertung zählt dagegen am Schließungstag (Z2) — die Fußnote sagt das.
export default function FilterAuswertung({
  auswertung,
  fehler,
  mitZeitraum,
}: {
  auswertung: Auswertung | null
  fehler: string | null
  // Ist ein Zeitraum gewählt? Die Zahl der Positionen gilt dann ohne ihn (die
  // Summe dagegen nur für dort geschlossene Strukturen).
  mitZeitraum: boolean
}): JSX.Element {
  if (fehler) {
    return (
      <section className="fehler">
        <h3>Die Auswertung konnte nicht geladen werden</h3>
        <p>{fehler}</p>
      </section>
    )
  }
  if (auswertung === null) return <p className="laedt">Lade Auswertung …</p>

  const { ergebnis } = auswertung
  const letzterTag = auswertung.tage.length > 0 ? auswertung.tage[auswertung.tage.length - 1] : null

  return (
    <section className="auswertung">
      <h3>Ergebnis der gefilterten Positionen</h3>
      <dl className="kopf">
        <div>
          <dt
            title={
              mitZeitraum
                ? 'Zahl der Positionen, die die Filter erfüllen — der Zeitraum ist hier nicht angewendet.'
                : undefined
            }
          >
            Positionen in der Auswahl{mitZeitraum ? ' (ohne Zeitraum)' : ''}
          </dt>
          <dd>{ergebnis.anzahl_ketten}</dd>
        </div>
        <div>
          <dt>Abgeschlossene Strukturen</dt>
          <dd>{ergebnis.anzahl_strukturen}</dd>
        </div>
        <div>
          <dt>Ergebnis netto (EUR)</dt>
          <dd>
            <Betrag wert={ergebnis.summe_netto_eur} />
          </dd>
        </div>
        <div>
          <dt>
            Maximaler Drawdown
            {auswertung.max_drawdown_datum ? ` (${datumDe(auswertung.max_drawdown_datum)})` : ''}
          </dt>
          <dd>
            <Betrag wert={auswertung.max_drawdown_eur} />
          </dd>
        </div>
        <div>
          <dt>Stand am letzten Tag</dt>
          <dd>
            <Betrag wert={letzterTag ? letzterTag.kumuliert_eur : null} />
          </dd>
        </div>
      </dl>

      {ergebnis.anzahl_kurs_fehlt > 0 ? (
        <p className="sicht">
          {ergebnis.anzahl_kurs_fehlt} Geschäft(e) ohne Wechselkurs sind in der Summe nicht
          enthalten.
        </p>
      ) : null}

      {auswertung.tage.length === 0 ? (
        <p className="hinweis">Keine abgeschlossenen Positionen in dieser Auswahl.</p>
      ) : (
        <>
          <Linie punkte={auswertung.tage.map((t) => ({ x: t.datum, y: t.kumuliert_eur }))} />
          <Balken balken={auswertung.monate.map((m) => ({ x: m.monat, y: m.summe_netto_eur }))} />
        </>
      )}

      <p className="sicht fussnote">
        Kontosicht, EUR. Die Filter wählen ganze Positionen (Ketten): Von einer gewählten Position
        zählen alle Strukturen, auch früher geschlossene Rolls — deshalb kann die Kurve vor einem
        „Geschlossen von“ beginnen. Ergebnisse zählen am Tag der Schließung; ein gewählter Zeitraum begrenzt
        daher die Auswertung auf dort geschlossene Positionen, die Liste darunter zeigt dagegen
        alle im Zeitraum aktiven.{' '}
        {ergebnis.lose_legs_eingeschlossen
          ? 'Enthalten sind auch Aktiengeschäfte ohne zugehörige Position (z. B. aus Zuteilungen), soweit sie zu Basiswert, Klasse, Währung und Zeitraum der Auswahl passen.'
          : 'Ohne Aktiengeschäfte ohne zugehörige Position: Strategie, Seite, Endzustand und Rolls kennen sie nicht, sie fallen bei diesen Filtern heraus.'}
      </p>
    </section>
  )
}
