import { useEffect, useState } from "react";
import type { BacktestPaar, Backtests as Daten } from "./api";
import {
  entscheideBacktest,
  fehlerText,
  holeBacktestPaare,
  holeBacktests,
} from "./api";
import Betrag from "./Betrag";
import { datumDe, zeitDe } from "./format";

// AP-12a: Option-Omega-Backtests gegen die Bots. Zuordnung und alle Beträge
// kommen fertig aus GET /backtests (Vertrag 8) — USD je Kontrakt.

const STATUS: Record<string, string> = {
  vorschlag: "Vorschlag",
  bestaetigt: "bestätigt",
  abgelehnt: "abgelehnt",
};

const ART: Record<string, { text: string; hinweis: string }> = {
  paar: { text: "beide", hinweis: "Backtest und Bot haben gehandelt" },
  nur_backtest: {
    text: "nur Backtest",
    hinweis: "Der Backtest hat gehandelt, der Bot an diesem Tag nicht",
  },
  nur_live: {
    text: "nur Bot",
    hinweis: "Der Bot hat gehandelt, kein Backtest-Trade passt dazu",
  },
  offen: { text: "offen", hinweis: "Noch nicht abgeschlossen" },
};

type Auswahl = { oo: string; oa: string };

export default function Backtests(): JSX.Element {
  const [daten, setzeDaten] = useState<Daten | null>(null);
  const [fehler, setzeFehler] = useState<string | null>(null);
  const [stand, setzeStand] = useState(0);
  const [auswahl, setzeAuswahl] = useState<Auswahl | null>(null);
  const [paare, setzePaare] = useState<BacktestPaar[] | null>(null);

  useEffect(() => {
    holeBacktests()
      .then(setzeDaten)
      .catch((e) => setzeFehler(fehlerText(e)));
  }, [stand]);

  useEffect(() => {
    setzePaare(null);
    if (auswahl === null) return;
    holeBacktestPaare(auswahl.oo, auswahl.oa)
      .then(setzePaare)
      .catch((e) => setzeFehler(fehlerText(e)));
  }, [auswahl, stand]);

  function entscheide(
    oo: string,
    oa: string,
    status: "bestaetigt" | "abgelehnt" | "vorschlag",
  ): void {
    entscheideBacktest(oo, oa, status)
      .then(() => setzeStand((s) => s + 1))
      .catch((e) => setzeFehler(fehlerText(e)));
  }

  if (fehler) {
    return (
      <section className="fehler">
        <h2>Die Backtests konnten nicht geladen werden</h2>
        <p>{fehler}</p>
      </section>
    );
  }
  if (daten === null) return <p className="laedt">Lade Backtests …</p>;
  if (daten.zuordnungen.length === 0 && daten.ohne_zuordnung.length === 0) {
    return (
      <section className="backtests">
        <h2>Backtests</h2>
        <p className="sicht">
          Noch keine Option-Omega-Exporte eingelesen. CSV nach{" "}
          <code>C:\Trading\oo</code> legen (wird beim Abruf eingelesen) oder{" "}
          <code>journal import-optionomega &lt;datei&gt;</code>.
        </p>
      </section>
    );
  }

  return (
    <section className="backtests">
      <h2>Backtests ↔ Bots</h2>
      <p className="sicht">
        Welcher Backtest gehört zu welchem Bot, errechnet aus den Trades selbst:
        gleicher Tag, Uhrzeit auf 20 Minuten, gleiche Struktur (Legs, Seiten,
        Laufzeiten, Breite). Vorschläge prüfen und bestätigen oder ablehnen.
      </p>

      <h3>Zuordnung</h3>
      <div className="tabelle-rahmen">
        <table className="strategie-tabelle">
          <thead>
            <tr>
              <th>Backtest (Option Omega)</th>
              <th>Bot (OptionApp)</th>
              <th
                className="zahl"
                title="Gepaarte Trades / alle Trades des Backtests"
              >
                Treffer
              </th>
              <th
                className="zahl"
                title="Anteil an allen Treffern dieses Backtests"
              >
                Anteil
              </th>
              <th>Zeitraum der Treffer</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {daten.zuordnungen.map((z) => (
              <tr
                key={`${z.oo_strategie}|${z.oa_strategie}`}
                className={z.status === "abgelehnt" ? "gedimmt" : undefined}
              >
                <td>{z.oo_strategie}</td>
                <td>{z.oa_strategie}</td>
                <td className="zahl">
                  {z.treffer} / {z.oo_anzahl}
                </td>
                <td className="zahl">
                  {(Number(z.anteil) * 100).toFixed(0)} %
                  {z.eindeutig ? " ✓" : ""}
                </td>
                <td>
                  {z.erster
                    ? `${datumDe(z.erster)} – ${datumDe(z.letzter)}`
                    : "—"}
                </td>
                <td title={z.erkennung === "heuristik" ? "errechnet" : "von Hand"}>
                  {STATUS[z.status]}
                </td>
                <td className="knoepfe">
                  {z.status === "vorschlag" ? (
                    <>
                      <button
                        type="button"
                        onClick={() =>
                          entscheide(z.oo_strategie, z.oa_strategie, "bestaetigt")
                        }
                      >
                        bestätigen
                      </button>{" "}
                      <button
                        type="button"
                        onClick={() =>
                          entscheide(z.oo_strategie, z.oa_strategie, "abgelehnt")
                        }
                      >
                        ablehnen
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      onClick={() =>
                        entscheide(z.oo_strategie, z.oa_strategie, "vorschlag")
                      }
                    >
                      zurücknehmen
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {daten.ohne_zuordnung.length > 0 && (
        <p className="sicht">
          Ohne Bot:{" "}
          {daten.ohne_zuordnung
            .map((o) => `${o.oo_strategie} (${o.anzahl} Trades)`)
            .join(" · ")}
        </p>
      )}

      <h3>Live gegen Backtest, je Kontrakt</h3>
      <div className="tabelle-rahmen">
        <table className="strategie-tabelle">
          <thead>
            <tr>
              <th>Backtest</th>
              <th>Bot</th>
              <th className="zahl">beide</th>
              <th className="zahl">Backtest</th>
              <th className="zahl">Bot</th>
              <th className="zahl" title="Bot − Backtest">
                Differenz
              </th>
              <th className="zahl" title={ART.nur_backtest.hinweis}>
                nur Backtest
              </th>
              <th className="zahl" title={ART.nur_live.hinweis}>
                nur Bot
              </th>
              <th className="zahl">offen</th>
            </tr>
          </thead>
          <tbody>
            {daten.vergleich.map((v) => {
              const gewaehlt =
                auswahl?.oo === v.oo_strategie && auswahl?.oa === v.oa_strategie;
              return (
                <tr
                  key={`${v.oo_strategie}|${v.oa_strategie}`}
                  className={gewaehlt ? "gewaehlt klickbar" : "klickbar"}
                  onClick={() =>
                    setzeAuswahl(
                      gewaehlt ? null : { oo: v.oo_strategie, oa: v.oa_strategie },
                    )
                  }
                >
                  <td>{v.oo_strategie}</td>
                  <td>{v.oa_strategie}</td>
                  <td className="zahl">{v.paare}</td>
                  <td className="zahl">
                    <Betrag wert={v.summe_backtest} waehrung="USD" />
                  </td>
                  <td className="zahl">
                    <Betrag wert={v.summe_live} waehrung="USD" />
                  </td>
                  <td className="zahl">
                    <Betrag wert={v.differenz} waehrung="USD" />
                  </td>
                  <td className="zahl">
                    {v.nur_backtest ? (
                      <>
                        {v.nur_backtest} ·{" "}
                        <Betrag wert={v.summe_nur_backtest} waehrung="USD" />
                      </>
                    ) : (
                      ""
                    )}
                  </td>
                  <td className="zahl">
                    {v.nur_live ? (
                      <>
                        {v.nur_live} ·{" "}
                        <Betrag wert={v.summe_nur_live} waehrung="USD" />
                      </>
                    ) : (
                      ""
                    )}
                  </td>
                  <td className="zahl">{v.offen || ""}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="sicht fussnote">
        Bot = OA-Gewinn je Trade (nicht das IB-Ergebnis, das zwischen Bots
        verrechnet wird), geteilt durch die Kontrakte; Backtest = OO-P/L je
        Kontrakt. „nur Backtest“ zählt nur Tage, an denen der Bot lief; „nur
        Bot“ nur Tage im Zeitraum des Backtests. Zeile anklicken für die
        einzelnen Trades.
      </p>

      {auswahl && (
        <>
          <h3>
            {auswahl.oo} ↔ {auswahl.oa}
          </h3>
          {paare === null ? (
            <p className="laedt">Lade Trades …</p>
          ) : (
            <div className="tabelle-rahmen">
              <table className="strategie-tabelle">
                <thead>
                  <tr>
                    <th>Art</th>
                    <th>Backtest</th>
                    <th>Bot</th>
                    <th>OA-Trade</th>
                    <th className="zahl">Kontrakte</th>
                    <th className="zahl">Backtest</th>
                    <th className="zahl">Bot</th>
                    <th className="zahl">Differenz</th>
                  </tr>
                </thead>
                <tbody>
                  {paare.map((p, i) => (
                    <tr key={i}>
                      <td title={ART[p.art].hinweis}>{ART[p.art].text}</td>
                      <td>{zeitDe(p.zeit_backtest)}</td>
                      <td>{zeitDe(p.zeit_live)}</td>
                      <td>{p.oa_trade ?? "—"}</td>
                      <td className="zahl">
                        {p.kontrakte_backtest ?? "—"} / {p.kontrakte_live ?? "—"}
                      </td>
                      <td className="zahl">
                        {p.pl_backtest === null ? (
                          "—"
                        ) : (
                          <Betrag wert={p.pl_backtest} waehrung="USD" />
                        )}
                      </td>
                      <td className="zahl">
                        {p.pl_live === null ? (
                          "—"
                        ) : (
                          <Betrag wert={p.pl_live} waehrung="USD" />
                        )}
                      </td>
                      <td className="zahl">
                        {p.differenz === null ? (
                          "—"
                        ) : (
                          <Betrag wert={p.differenz} waehrung="USD" />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  );
}
