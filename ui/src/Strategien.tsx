import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { StrategieZeile, Strategien as Daten } from "./api";
import { fehlerText, holeStrategien } from "./api";
import Betrag from "./Betrag";
import { betrag, datumDe, prozent } from "./format";
import { useZeitraum } from "./zeitraum";

// AP-06sc: Strategie-Scorecard. Alle Werte kommen fertig aus GET /strategien
// (Vertrag 8). Die Sortierung über die Spaltenköpfe ordnet nur Zeilen — dafür
// wird der Text in eine Zahl gewandelt, angezeigt wird weiter der API-Text.

type Spalte =
  | "strategie"
  | "anzahl"
  | "trefferquote"
  | "summe_eur"
  | "durchschnitt_eur"
  | "durchschnitt_gewinn_eur"
  | "durchschnitt_verlust_eur"
  | "profit_faktor"
  | "groesster_verlust_eur"
  | "max_drawdown_eur"
  | "zuteilungsquote"
  | "haltedauer_tage";

const SPALTEN: { id: Spalte; titel: string; hinweis?: string }[] = [
  { id: "strategie", titel: "Strategie" },
  {
    id: "anzahl",
    titel: "Positionen",
    hinweis: "Geschlossene Positionen im Zeitraum; dahinter offene",
  },
  {
    id: "trefferquote",
    titel: "Treffer",
    hinweis: "Anteil der Positionen mit Gewinn",
  },
  { id: "summe_eur", titel: "Summe netto" },
  {
    id: "durchschnitt_eur",
    titel: "Ø je Position",
    hinweis: "Erwartungswert je Position",
  },
  { id: "durchschnitt_gewinn_eur", titel: "Ø Gewinn" },
  { id: "durchschnitt_verlust_eur", titel: "Ø Verlust" },
  {
    id: "profit_faktor",
    titel: "Profit-Faktor",
    hinweis:
      "Summe der Gewinne ÷ Summe der Verluste (über 1 = verdient); „—“ ohne Verluste",
  },
  { id: "groesster_verlust_eur", titel: "Größter Verlust" },
  {
    id: "max_drawdown_eur",
    titel: "Max. Drawdown",
    hinweis:
      "Größter Rückgang der aufsummierten Ergebnisse in der Reihenfolge der Schließung",
  },
  {
    id: "zuteilungsquote",
    titel: "Zuteilungen",
    hinweis: "Anteil der Positionen mit Zuteilung (Aktie geliefert)",
  },
  {
    id: "haltedauer_tage",
    titel: "Ø Tage",
    hinweis: "Durchschnittliche Haltedauer in Tagen",
  },
];

function sortierwert(z: StrategieZeile, s: Spalte): number | string {
  if (s === "strategie") return z.strategie ?? "";
  if (s === "anzahl") return z.anzahl;
  const wert = z[s];
  return wert === null ? Number.NEGATIVE_INFINITY : Number(wert);
}

export default function Strategien(): JSX.Element {
  const [zeitraum] = useZeitraum();
  const [daten, setzeDaten] = useState<Daten | null>(null);
  const [fehler, setzeFehler] = useState<string | null>(null);
  const [sortierung, setzeSortierung] = useState<{
    spalte: Spalte;
    ab: boolean;
  }>({
    spalte: "summe_eur",
    ab: true,
  });
  const [mitOhne, setzeMitOhne] = useState(true);

  useEffect(() => {
    setzeDaten(null);
    setzeFehler(null);
    holeStrategien(zeitraum.von, zeitraum.bis)
      .then(setzeDaten)
      .catch((e) => setzeFehler(fehlerText(e)));
  }, [zeitraum.von, zeitraum.bis]);

  if (fehler) {
    return (
      <section className="fehler">
        <h2>Die Strategien konnten nicht geladen werden</h2>
        <p>{fehler}</p>
      </section>
    );
  }
  if (daten === null) return <p className="laedt">Lade Strategien …</p>;

  const zeilen = daten.zeilen
    .filter((z) => mitOhne || z.strategie !== null)
    .sort((a, b) => {
      const x = sortierwert(a, sortierung.spalte);
      const y = sortierwert(b, sortierung.spalte);
      const v = x < y ? -1 : x > y ? 1 : 0;
      return sortierung.ab ? -v : v;
    });

  function sortiere(s: Spalte): void {
    setzeSortierung((alt) =>
      alt.spalte === s
        ? { spalte: s, ab: !alt.ab }
        : { spalte: s, ab: s !== "strategie" },
    );
  }

  return (
    <section className="strategien">
      <h2>Strategien</h2>
      <p className="sicht">
        Je OptionApp-Strategie die im Zeitraum geschlossenen Positionen
        (Kontosicht, netto in EUR, Kurs des jeweiligen Tages). Zuteilungen und
        Covered Calls gehören zur Position, die sie ausgelöst hat. Spaltenkopf
        klicken zum Sortieren.
      </p>
      <label className="umschalter">
        <input
          type="checkbox"
          checked={mitOhne}
          onChange={(e) => setzeMitOhne(e.target.checked)}
        />{" "}
        Positionen ohne Strategie zeigen
      </label>
      <div className="tabelle-rahmen">
        <table className="strategie-tabelle">
          <thead>
            <tr>
              {SPALTEN.map((s) => (
                <th
                  key={s.id}
                  title={s.hinweis}
                  className={s.id === "strategie" ? "" : "zahl"}
                  onClick={() => sortiere(s.id)}
                  aria-sort={
                    sortierung.spalte === s.id
                      ? sortierung.ab
                        ? "descending"
                        : "ascending"
                      : undefined
                  }
                >
                  {s.titel}
                  {sortierung.spalte === s.id
                    ? sortierung.ab
                      ? " ▼"
                      : " ▲"
                    : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {zeilen.map((z) => (
              <tr key={z.strategie ?? "(ohne)"}>
                <td>
                  {z.strategie === null ? (
                    <em>ohne Strategie</em>
                  ) : (
                    <Link to={`/?strategie=${encodeURIComponent(z.strategie)}`}>
                      {z.strategie}
                    </Link>
                  )}
                </td>
                <td
                  className="zahl"
                  title={
                    z.kurs_fehlt
                      ? `${z.kurs_fehlt} ohne Wechselkurs`
                      : undefined
                  }
                >
                  {z.anzahl}
                  {z.offen ? (
                    <span className="nebenbei"> +{z.offen} offen</span>
                  ) : null}
                </td>
                <td className="zahl">{prozent(z.trefferquote)}</td>
                <td className="zahl">
                  <Betrag wert={z.summe_eur} />
                </td>
                <td className="zahl">
                  <Betrag wert={z.durchschnitt_eur} />
                </td>
                <td className="zahl">
                  <Betrag wert={z.durchschnitt_gewinn_eur} />
                </td>
                <td className="zahl">
                  <Betrag wert={z.durchschnitt_verlust_eur} />
                </td>
                <td className="zahl">
                  {z.profit_faktor === null ? "—" : betrag(z.profit_faktor)}
                </td>
                <td className="zahl">
                  <Betrag wert={z.groesster_verlust_eur} />
                </td>
                <td className="zahl">
                  <Betrag wert={z.max_drawdown_eur} />
                </td>
                <td className="zahl">{prozent(z.zuteilungsquote)}</td>
                <td
                  className="zahl"
                  title={
                    z.erste_schliessung
                      ? `geschlossen ${datumDe(z.erste_schliessung)} – ${datumDe(z.letzte_schliessung)}`
                      : undefined
                  }
                >
                  {z.haltedauer_tage === null
                    ? "—"
                    : z.haltedauer_tage.replace(".", ",")}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>Überleitung zum realisierten Ergebnis</h3>
      <table className="bestandteile">
        <tbody>
          <tr>
            <td>Summe aller Strategien (geschlossene Positionen)</td>
            <td className="zahl">
              <Betrag wert={daten.summe_strategien_eur} />
            </td>
          </tr>
          <tr>
            <td title="Bereits geschlossene Teile noch offener Positionen (z. B. Roll-Schritte); mit Zeitraum auch Positionen über die Zeitraumgrenze">
              + realisierte Teile offener Positionen
            </td>
            <td className="zahl">
              <Betrag wert={daten.abgrenzung_eur} />
            </td>
          </tr>
          <tr>
            <td title="Geschäfte, die zu keiner Position gehören (z. B. Aktien aus Zuteilungen ohne Optionsbuchung)">
              + Geschäfte ohne Position
            </td>
            <td className="zahl">
              <Betrag wert={daten.ohne_position_eur} />
            </td>
          </tr>
          <tr className="summe">
            <td>= Realisiert netto (wie Dashboard)</td>
            <td className="zahl">
              <Betrag wert={daten.realisiert_gesamt_eur} />
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  );
}
