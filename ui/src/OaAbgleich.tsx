import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { OaAbgleich as Daten } from "./api";
import { fehlerText, holeOaAbgleich } from "./api";
import Betrag from "./Betrag";
import { zeitDe } from "./format";
import { useZeitraum } from "./zeitraum";

// AP-13ab: Abgleich OA ↔ IB. Alle Beträge kommen fertig aus GET /oa-abgleich
// (Vertrag 8) — in der Währung des Trades, nicht umgerechnet.

const GRUENDE: Record<string, { text: string; hinweis: string }> = {
  gleich: { text: "gleich", hinweis: "OA und IB stimmen auf 5 Cent" },
  verrechnet: {
    text: "verrechnet",
    hinweis:
      "Der Trade teilt Kontrakte mit anderen OA-Trades; IB hat sie im Konto gegeneinander geschlossen. Die Gruppe stimmt, die Aufteilung zwischen den Trades nicht.",
  },
  gering: {
    text: "gering",
    hinweis: "Abweichung bis 1,00 — meist OAs geschätzte Kommission",
  },
  zuteilung: {
    text: "Zuteilung",
    hinweis: "Aktien aus einer Zuteilung — OA rechnet sie nicht ein, IB schon",
  },
  schaetzung: {
    text: "OA-Schätzung",
    hinweis:
      "OA hat den Abrechnungskurs am Verfall nur geschätzt („EXPIRED (estimated)“)",
  },
  sonst: {
    text: "ungeklärt",
    hinweis: "Abweichung ohne bekannte Ursache — bitte prüfen",
  },
  offen: { text: "offen", hinweis: "Noch nicht abgeschlossen" },
  fehlt: {
    text: "fehlt bei IB",
    hinweis: "Keine IB-Ausführung mit dieser OA-Nummer",
  },
  waehrung: {
    text: "Währung",
    hinweis:
      "OA nennt den Gewinn nur umgerechnet (USD) — kein Vergleich möglich",
  },
};

const AUSWAHL = ["ungeklärt und Zuteilung", "alle Abweichungen"] as const;

export default function OaAbgleich(): JSX.Element {
  const [zeitraum] = useZeitraum();
  const [daten, setzeDaten] = useState<Daten | null>(null);
  const [fehler, setzeFehler] = useState<string | null>(null);
  const [auswahl, setzeAuswahl] = useState<(typeof AUSWAHL)[number]>(
    "ungeklärt und Zuteilung",
  );

  useEffect(() => {
    setzeDaten(null);
    setzeFehler(null);
    holeOaAbgleich(zeitraum.von, zeitraum.bis)
      .then(setzeDaten)
      .catch((e) => setzeFehler(fehlerText(e)));
  }, [zeitraum.von, zeitraum.bis]);

  if (fehler) {
    return (
      <section className="fehler">
        <h2>Der Abgleich konnte nicht geladen werden</h2>
        <p>{fehler}</p>
      </section>
    );
  }
  if (daten === null) return <p className="laedt">Lade Abgleich …</p>;

  const trades = daten.abweichungen.filter((t) =>
    auswahl === "alle Abweichungen"
      ? true
      : t.grund === "sonst" || t.grund === "zuteilung",
  );

  return (
    <section className="oa-abgleich">
      <h2>Abgleich OA ↔ IB</h2>
      <p className="sicht">
        Je OptionApp-Trade das Ergebnis laut OA gegen das, was IB gebucht hat
        (Kontosicht, in der Währung des Trades, nach Kommission; zugeteilte
        Aktien gehören zum Trade). {daten.anzahl_gleich} von{" "}
        {daten.anzahl_trades} Trades stimmen auf 5 Cent.
      </p>

      <div className="tabelle-rahmen">
        <table className="strategie-tabelle">
          <thead>
            <tr>
              <th>Strategie</th>
              <th className="zahl">Trades</th>
              <th className="zahl" title={GRUENDE.gleich.hinweis}>
                gleich
              </th>
              <th className="zahl" title={GRUENDE.verrechnet.hinweis}>
                verrechnet
              </th>
              <th className="zahl" title={GRUENDE.gering.hinweis}>
                gering
              </th>
              <th
                className="zahl"
                title="Zuteilung, OA-Schätzung oder ungeklärt"
              >
                abweichend
              </th>
              <th className="zahl">offen / fehlt</th>
              <th className="zahl">Summe OA</th>
              <th className="zahl">Summe IB</th>
              <th className="zahl" title="IB − OA">
                Differenz
              </th>
            </tr>
          </thead>
          <tbody>
            {daten.strategien.map((s) => (
              <tr key={`${s.strategie ?? ""}-${s.waehrung}`}>
                <td>
                  {s.strategie === null ? (
                    <em>ohne Strategie</em>
                  ) : (
                    <Link to={`/?strategie=${encodeURIComponent(s.strategie)}`}>
                      {s.strategie}
                    </Link>
                  )}
                </td>
                <td className="zahl">{s.anzahl}</td>
                <td className="zahl">{s.gleich}</td>
                <td className="zahl">{s.verrechnet || ""}</td>
                <td className="zahl">{s.gering || ""}</td>
                <td className="zahl">{s.abweichend || ""}</td>
                <td className="zahl">
                  {s.offen || s.fehlt ? `${s.offen} / ${s.fehlt}` : ""}
                  {s.waehrung_unklar ? ` · ${s.waehrung_unklar} Währ.` : ""}
                </td>
                <td className="zahl">
                  <Betrag wert={s.summe_oa} waehrung={s.waehrung} />
                </td>
                <td className="zahl">
                  <Betrag wert={s.summe_ib} waehrung={s.waehrung} />
                </td>
                <td className="zahl">
                  <Betrag wert={s.differenz} waehrung={s.waehrung} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="sicht fussnote">
        Summen nur über vergleichbare Trades (ohne offene, fehlende und solche,
        die OA nur umgerechnet nennt). „verrechnet“: Teilen sich Bots denselben
        Kontrakt, schließt IB nach FIFO über das ganze Konto — das Ergebnis
        wandert zwischen Trades und Strategien, die Summe der Gruppe stimmt.
        Eine Auswertung ganz ohne diese Verschiebung bräuchte eine eigene
        Paarung je OA-Trade (vorgemerkt).
      </p>

      <h3>Trades mit Abweichung</h3>
      <div className="diagramm-wahl" role="group">
        {AUSWAHL.map((a) => (
          <button
            key={a}
            type="button"
            aria-pressed={auswahl === a}
            onClick={() => setzeAuswahl(a)}
          >
            {a}
          </button>
        ))}
      </div>
      <div className="tabelle-rahmen">
        <table className="strategie-tabelle">
          <thead>
            <tr>
              <th>OA-Trade</th>
              <th>Strategie</th>
              <th>Status OA</th>
              <th>Schluss</th>
              <th className="zahl">OA</th>
              <th className="zahl">IB</th>
              <th className="zahl">Differenz</th>
              <th>Einordnung</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t) => (
              <tr key={t.oa_trade}>
                <td>{t.oa_trade}</td>
                <td>{t.strategie ?? "—"}</td>
                <td>{t.status}</td>
                <td>{zeitDe(t.schluss_zeit)}</td>
                <td className="zahl">
                  <Betrag wert={t.oa_profit} waehrung={t.waehrung} />
                </td>
                <td className="zahl">
                  {t.ib_netto === null ? (
                    "—"
                  ) : (
                    <Betrag wert={t.ib_netto} waehrung={t.waehrung} />
                  )}
                </td>
                <td className="zahl">
                  {t.differenz === null ? (
                    "—"
                  ) : (
                    <Betrag wert={t.differenz} waehrung={t.waehrung} />
                  )}
                </td>
                <td title={GRUENDE[t.grund]?.hinweis}>
                  {GRUENDE[t.grund]?.text ?? t.grund}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
