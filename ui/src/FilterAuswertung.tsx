import { useState } from 'react'
import type { Auswertung } from './api'
import { datumDe } from './format'
import Betrag from './Betrag'
import Balken from './diagramm/Balken'
import { monatKurz } from './diagramm/skala'

// AP-08g2b: Verlauf und Ergebnis der gefilterten Positionen (GET /auswertung,
// AP-07f). Alles kommt als Text aus der API und wird nur formatiert (D2,
// Vertrag 8): Summe, Drawdown und Kurve rechnet das Backend.
//
// AP-07fu (11.10.2026, Wunsch des Nutzers): keine aufsummierte Linie mehr,
// sondern der realisierte Gewinn **je Tag** (taggenau, am Tag der Schließung);
// sind Positionen der Auswahl noch offen, steht ihr unrealisiertes Ergebnis als
// eigener, heller Balken am Ende. Darunter Wochen (Vorgabe) oder Monate.
//
// Zeitraum: In der Positionsliste heißt „im Zeitraum" aktiv (Z3); die
// Auswertung zählt dagegen am Schließungstag (Z2) — die Fußnote sagt das.

const UNREALISIERT = 'unrealisiert'

function tagKurz(iso: string): string {
  if (iso === UNREALISIERT) return 'offen'
  return `${iso.slice(8, 10)}.${iso.slice(5, 7)}.`
}

function wocheKurz(schluessel: string): string {
  const [jahr, woche] = schluessel.split('-W')
  return `KW ${woche}/${jahr.slice(2)}`
}

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
  const [einteilung, setzeEinteilung] = useState<'woche' | 'monat'>('woche')

  if (fehler) {
    return (
      <section className="fehler">
        <h3>Die Auswertung konnte nicht geladen werden</h3>
        <p>{fehler}</p>
      </section>
    )
  }
  if (auswertung === null) return <p className="laedt">Lade Auswertung …</p>

  const { ergebnis, unrealisiert } = auswertung
  const mitUnrealisiert =
    unrealisiert !== null && unrealisiert.stichtag !== null && unrealisiert.anzahl_legs > 0
  const tagesbalken = auswertung.tage.map((t) => ({ x: t.datum, y: t.netto_eur }))
  if (mitUnrealisiert && unrealisiert !== null) {
    tagesbalken.push({ x: UNREALISIERT, y: unrealisiert.eur })
  }
  const periodenbalken =
    einteilung === 'woche'
      ? auswertung.wochen.map((w) => ({ x: w.schluessel, y: w.summe_netto_eur }))
      : auswertung.monate.map((m) => ({ x: m.monat, y: m.summe_netto_eur }))

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
          <dt>Realisiert netto (EUR)</dt>
          <dd>
            <Betrag wert={ergebnis.summe_netto_eur} />
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

      {tagesbalken.length === 0 ? (
        <p className="hinweis">Keine abgeschlossenen Positionen in dieser Auswahl.</p>
      ) : (
        <>
          <h4>Realisiert je Tag{mitUnrealisiert ? ' und offene Positionen' : ''}</h4>
          <Balken balken={tagesbalken} beschriftung={tagKurz} hervorheben={[UNREALISIERT]} />
          <div className="diagramm-wahl" role="group">
            {(['woche', 'monat'] as const).map((wert) => (
              <button
                key={wert}
                type="button"
                aria-pressed={einteilung === wert}
                onClick={() => setzeEinteilung(wert)}
              >
                {wert === 'woche' ? 'Wochen' : 'Monate'}
              </button>
            ))}
          </div>
          <Balken
            balken={periodenbalken}
            beschriftung={einteilung === 'woche' ? wocheKurz : monatKurz}
          />
        </>
      )}

      <p className="sicht fussnote">
        Kontosicht, EUR. Realisiert zählt am Tag der Schließung; der helle, gestrichelte Balken
        „offen“ ist das unrealisierte Ergebnis der noch offenen Positionen der Auswahl (IBs letzter
        Marktwert gegen den Einstand des Journals, Stand des letzten Berichts). Die Filter wählen
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
