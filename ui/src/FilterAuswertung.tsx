import type { Auswertung } from './api'
import { datumDe } from './format'
import Betrag from './Betrag'
import ZweiLinien from './diagramm/ZweiLinien'

// AP-08g2b: Verlauf und Ergebnis der gefilterten Positionen (GET /auswertung,
// AP-07f). Alles kommt als Text aus der API und wird nur formatiert (D2,
// Vertrag 8): Summe, Drawdown und Kurve rechnet das Backend.
//
// AP-07fv (11.10.2026, Wunsch des Nutzers): ein einziges Diagramm — die
// aufsummierte realisierte Linie Tag für Tag (`verlauf`, auch Tage ohne
// Schließung). Sind Positionen der Auswahl offen, verlängert eine gestrichelte
// Linie bis zum Stichtag des Bestands um das Unrealisierte. Im Kopf steht das
// Realisierte in EUR und je Positionswährung (nativ).
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

  const { ergebnis, unrealisiert, verlauf } = auswertung
  const mitUnrealisiert =
    unrealisiert !== null && unrealisiert.stichtag !== null && unrealisiert.anzahl_legs > 0
  const linie = verlauf.map((p) => ({ x: p.datum, y: p.kumuliert_eur }))
  // Gestrichelt: vom letzten realisierten Punkt (Stand bis dahin) zum Stichtag
  // mit realisiert + unrealisiert — beide Werte liefert die API.
  const ausblick =
    mitUnrealisiert && unrealisiert !== null && unrealisiert.stichtag !== null
      ? [
          ...(linie.length > 0 ? [linie[linie.length - 1]] : []),
          { x: unrealisiert.stichtag, y: unrealisiert.mit_realisiert_eur },
        ]
      : null

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
          <dt>Realisiert netto</dt>
          <dd>
            <Betrag wert={ergebnis.summe_netto_eur} />
            {auswertung.netto_je_waehrung.some((z) => z.waehrung !== 'EUR') ? (
              <span className="je-waehrung">
                in Positionswährung:{' '}
                {auswertung.netto_je_waehrung.map((z, i) => (
                  <span key={z.waehrung}>
                    {i > 0 ? ' · ' : ''}
                    <Betrag wert={z.summe} waehrung={z.waehrung} />
                  </span>
                ))}
              </span>
            ) : null}
          </dd>
        </div>
        <div>
          <dt
            title="Offene Positionen der Auswahl, bewertet mit IBs letztem Marktwert gegen den Einstand des Journals"
          >
            Unrealisiert{unrealisiert?.stichtag ? ` (${datumDe(unrealisiert.stichtag)})` : ''}
          </dt>
          <dd>
            {unrealisiert === null || unrealisiert.stichtag === null ? (
              '—'
            ) : (
              <Betrag wert={unrealisiert.eur} />
            )}
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
      </dl>

      {ergebnis.anzahl_kurs_fehlt > 0 ? (
        <p className="sicht">
          {ergebnis.anzahl_kurs_fehlt} Geschäft(e) ohne Wechselkurs sind in der Summe nicht
          enthalten.
        </p>
      ) : null}
      {unrealisiert !== null && unrealisiert.ohne_kurs > 0 ? (
        <p className="sicht">
          {unrealisiert.ohne_kurs} offene(s) Leg(s) ohne Bestand laut IB — im Unrealisierten nicht
          enthalten.
        </p>
      ) : null}

      {linie.length === 0 && ausblick === null ? (
        <p className="hinweis">Keine abgeschlossenen Positionen in dieser Auswahl.</p>
      ) : (
        <ZweiLinien
          oben={linie.length > 0 ? linie : (ausblick ?? [])}
          unten={linie.length > 0 ? ausblick : null}
          gestrichelt
          legendeOben="Realisiert netto, aufsummiert (EUR)"
          legendeUnten={
            ausblick !== null && linie.length > 0
              ? `mit Unrealisiertem der offenen Positionen (${datumDe(unrealisiert?.stichtag ?? null)})`
              : null
          }
        />
      )}

      <p className="sicht fussnote">
        Kontosicht. Realisiert zählt am Tag der Schließung, in EUR zum Kurs des jeweiligen Tages;
        „in Positionswährung“ nennt dasselbe Ergebnis je Währung der Positionen, nicht
        umgerechnet (EUR-Summe ≠ Summe der Währungsbeträge). Die gestrichelte Linie ergänzt das unrealisierte Ergebnis der noch
        offenen Positionen der Auswahl (IBs letzter Marktwert gegen den Einstand des Journals, Stand
        des letzten Berichts). Die Filter wählen
        ganze Positionen (Ketten): Von einer gewählten Position zählen alle Strukturen, auch früher
        geschlossene Rolls. Ein gewählter Zeitraum begrenzt die Auswertung auf dort geschlossene
        Positionen, die Liste darunter zeigt dagegen alle im Zeitraum aktiven.{' '}
        {ergebnis.lose_legs_eingeschlossen
          ? 'Enthalten sind auch Aktiengeschäfte ohne zugehörige Position (z. B. aus Zuteilungen), soweit sie zu Basiswert, Klasse, Währung und Zeitraum der Auswahl passen.'
          : 'Ohne Aktiengeschäfte ohne zugehörige Position: Strategie, Seite, Endzustand und Rolls kennen sie nicht, sie fallen bei diesen Filtern heraus.'}
      </p>
    </section>
  )
}
