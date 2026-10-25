import { Fragment, useEffect, useState } from "react";
import type { BacktestPaar, Backtests as Daten } from "./api";
import {
  entscheideBacktest,
  fehlerText,
  holeBacktestPaare,
  holeBacktests,
} from "./api";
import BacktestPartner from "./BacktestPartner";
import Betrag from "./Betrag";
import { datumDe, zeitDe } from "./format";
import { useZeitraum } from "./zeitraum";

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

// AP-12c: Ursache je Paar — genau eine, in dieser Prüfreihenfolge.
// M07: alle beobachteten Unterschiede eines Paars (die „erste“ Ursache erklärt nicht zwingend den ganzen Betrag).
const ABWEICHUNG: Record<string, string> = {
  kontrakte: "Kontraktzahl",
  einstiegszeit: "Einstiegszeit",
  strikeauswahl: "Strikeauswahl",
  exit_art: "Art des Ausstiegs (Verfall gegen vorzeitig)",
  exit_zeit: "Zeitpunkt des Ausstiegs",
}

const URSACHE: Record<string, { text: string; hinweis: string }> = {
  kontrakte: {
    text: "Kontraktzahl",
    hinweis: "Backtest und Bot handeln verschieden viele Kontrakte",
  },
  toleranz: {
    text: "in Toleranz",
    hinweis: "Unterschied höchstens 10 USD je Kontrakt",
  },
  einstiegszeit: {
    text: "Einstiegszeit",
    hinweis: "Der Bot steigt mehr als 3 Minuten früher oder später ein",
  },
  strikeauswahl: {
    text: "Strikeauswahl",
    hinweis: "Der Bot wählt andere Strikes als der Backtest",
  },
  exit: {
    text: "Exit-Logik",
    hinweis:
      "Einer steigt vorzeitig aus, der andere läuft bis zum Verfall (oder mehr als 5 Minuten Unterschied)",
  },
  slippage: {
    text: "Slippage",
    hinweis: "Alles gleich außer den Fills — Rest der Differenz",
  },
};

type Auswahl = { oo: string; oa: string };

export default function Backtests(): JSX.Element {
  const [zeitraum] = useZeitraum();
  const [daten, setzeDaten] = useState<Daten | null>(null);
  const [fehler, setzeFehler] = useState<string | null>(null);
  const [stand, setzeStand] = useState(0);
  const [auswahl, setzeAuswahl] = useState<Auswahl | null>(null);
  const [paare, setzePaare] = useState<BacktestPaar[] | null>(null);

  useEffect(() => {
    holeBacktests(zeitraum.von, zeitraum.bis)
      .then(setzeDaten)
      .catch((e) => setzeFehler(fehlerText(e)));
  }, [stand, zeitraum.von, zeitraum.bis]);

  useEffect(() => {
    setzePaare(null);
    if (auswahl === null) return;
    holeBacktestPaare(auswahl.oo, auswahl.oa, zeitraum.von, zeitraum.bis)
      .then(setzePaare)
      .catch((e) => setzeFehler(fehlerText(e)));
  }, [auswahl, stand, zeitraum.von, zeitraum.bis]);

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
              const klick = () =>
                setzeAuswahl(
                  gewaehlt ? null : { oo: v.oo_strategie, oa: v.oa_strategie },
                );
              return (
                <Fragment key={`${v.oo_strategie}|${v.oa_strategie}`}>
                <tr
                  className={gewaehlt ? "gewaehlt klickbar" : "klickbar"}
                  onClick={klick}
                >
                  <td>{v.oo_strategie}</td>
                  <td className="bot">{v.oa_strategie}</td>
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
                {v.ursachen.length > 0 && (
                  <tr
                    className={gewaehlt ? "gewaehlt klickbar ursachenzeile" : "klickbar ursachenzeile"}
                    onClick={klick}
                  >
                    <td colSpan={9} className="ursachen">
                      <span className="beschriftung" title="Je Paar die erste erkannte Abweichung in fester Reihenfolge — keine kausale Zerlegung; weitere Unterschiede stehen in der Paarliste">Erste erkannte Abweichung je Paar (kein Nachweis der Ursache):</span>
                      {v.ursachen.map((u) => (
                        <span
                          key={u.ursache}
                          className="ursache"
                          title={URSACHE[u.ursache]?.hinweis}
                        >
                          {URSACHE[u.ursache]?.text ?? u.ursache} {u.anzahl}×{" "}
                          <Betrag wert={u.summe} waehrung="USD" />
                        </span>
                      ))}
                      {Number(v.kontrakt_effekt) !== 0 && (
                        <span
                          className="ursache"
                          title="Ergebnis des Bots, das durch abweichende Kontraktzahlen entsteht (Dollar insgesamt)"
                        >
                          · Kontrakt-Effekt <Betrag wert={v.kontrakt_effekt} waehrung="USD" />
                        </span>
                      )}
                    </td>
                  </tr>
                )}
                {(v.anzahl_einstieg ?? 0) > 0 && (
                  <tr
                    className={gewaehlt ? "gewaehlt klickbar ursachenzeile" : "klickbar ursachenzeile"}
                    onClick={klick}
                  >
                    <td colSpan={9} className="ursachen">
                      <span
                        className="beschriftung"
                        title="Prämie je Kontrakt laut tatsächlichen Fills des Bots minus Prämie des Backtests, nur Paare mit beiden Werten. Positiv = der Bot hat mehr Credit bekommen. Der Ausstieg lässt sich nicht vergleichen: der Export nennt keine Schlusskurse der Legs."
                      >
                        Einstiegs-Fills (Bot − Backtest, je Kontrakt):
                      </span>{" "}
                      <Betrag wert={v.summe_einstieg_abweichung ?? "0"} waehrung="USD" /> in {v.anzahl_einstieg} Paaren
                      {(v.anzahl_korrigiert ?? 0) > 0 && (
                        <span className="ursache"> · {v.anzahl_korrigiert} Partner manuell korrigiert</span>
                      )}
                    </td>
                  </tr>
                )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="sicht fussnote">
        Bot = OA-Gewinn je Trade (nicht das IB-Ergebnis, das zwischen Bots
        verrechnet wird), geteilt durch die Kontrakte; Backtest = OO-P/L je
        Kontrakt. „nur Backtest“ zählt nur Tage, an denen der Bot lief; „nur
        Bot“ nur Tage im Zeitraum des Backtests. Der Zeitraum oben begrenzt
        beide Seiten auf den Tag der Eröffnung — für den Monatsvergleich einfach
        den Monat wählen. Paare entstehen eins zu eins innerhalb von 90 Minuten.
        Zeile anklicken für die einzelnen Trades.
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
                    <th title="Einstieg des Bots minus Einstieg des Backtests">Versatz</th>
                    <th className="zahl">Kontrakte</th>
                    <th className="zahl">Backtest</th>
                    <th className="zahl">Bot</th>
                    <th className="zahl">Differenz</th>
                    <th>Ursache</th>
                    <th className="zahl" title="Eröffnungsprämie je Kontrakt: Bot laut Fills minus Backtest">Einstieg Bot − Backtest</th>
                    <th>Partner</th>
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
                        {p.zeitversatz_min === null
                          ? "—"
                          : `${p.zeitversatz_min > 0 ? "+" : ""}${p.zeitversatz_min} min`}
                      </td>
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
                      <td title={p.ursache ? URSACHE[p.ursache]?.hinweis : undefined}>
                        {p.ursache ? (
                          p.rest_unerklaert ? (
                            <span title="Keine Abweichung gefunden: der Betrag bleibt ungeklärt (Slippage ist nur eine Vermutung)">
                              ungeklärter Rest
                            </span>
                          ) : (
                            <>erste: {URSACHE[p.ursache]?.text ?? p.ursache}</>
                          )
                        ) : ""}
                        {(() => {
                          const weitere = (p.abweichungen ?? []).filter(
                            (a) => a !== p.ursache && !(p.ursache === "exit" && a.startsWith("exit")))
                          return weitere.length > 0 ? (
                            <div className="sicht">beobachtet außerdem: {weitere.map((a) => ABWEICHUNG[a] ?? a).join(", ")}</div>
                          ) : null
                        })()}
                        {p.art === "paar" && (p.ausstieg_backtest || p.ausstieg_live) && (
                          <div className="sicht">
                            Ausstieg: Backtest {p.ausstieg_backtest ?? "—"}, Bot {p.ausstieg_live ?? "—"}
                          </div>
                        )}
                      </td>
                      <td className="zahl">
                        {p.einstieg_abweichung == null ? (
                          "—"
                        ) : (
                          <Betrag wert={p.einstieg_abweichung} waehrung="USD" />
                        )}
                      </td>
                      <td>
                        <BacktestPartner
                          paar={p}
                          oaStrategie={auswahl.oa}
                          geaendert={() => setzeStand((n) => n + 1)}
                        />
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
