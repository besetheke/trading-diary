import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Betrag from "./Betrag";
import { fehlerText, holeBreakout, holeRoller, holeSystem, sendeMomentumBefehl, sendeRollerBefehl } from "./api";
import type { BreakoutStand, RollerAntwort, RollerKette, RollerStrategie, System } from "./api";
import { datumDe, zeitDe } from "./format";

// AP-14a: Cockpit-Gerüst. Die Station bündelt alle Werkzeuge in einer
// Oberfläche; dahinter bleiben eigenständige Dienste (Zielbild 12.10.2026).

const QUELLE: Record<string, string> = {
  flex: "IB Flex (Ausführungen, Bestand, NAV)",
  optionapp: "OptionApp-Export",
  optionomega: "Option-Omega-Backtests",
};

function useSystem(): [System | null, string | null, () => void] {
  const [daten, setzeDaten] = useState<System | null>(null);
  const [fehler, setzeFehler] = useState<string | null>(null);
  const [stand, setzeStand] = useState(0);
  useEffect(() => {
    holeSystem()
      .then(setzeDaten)
      .catch((e) => setzeFehler(fehlerText(e)));
  }, [stand]);
  return [daten, fehler, () => setzeStand((s) => s + 1)];
}

// Schalter für Momentum Lab (eigener Dienst auf Port 8501): Start ohne Fenster, Stopp nur für Momentum Lab selbst.
function MomentumSchalter({ an, neu }: { an: boolean | null; neu: () => void }): JSX.Element {
  const [arbeitet, setzeArbeitet] = useState(false);
  const [meldung, setzeMeldung] = useState<string | null>(null);
  function schalten(): void {
    const aktion = an ? "stop" : "start";
    setzeArbeitet(true);
    setzeMeldung(null);
    sendeMomentumBefehl(aktion)
      .then((r) => setzeMeldung(r.text))
      .catch((e) => setzeMeldung(fehlerText(e)))
      .finally(() => {
        // Der Start dauert einige Sekunden: mehrmals neu prüfen, statt auf einen Klick zu warten.
        [1500, 4000, 8000, 14000].forEach((ms) => window.setTimeout(neu, ms));
        window.setTimeout(() => setzeArbeitet(false), 14000);
      });
  }
  return (
    <span className="momentum-schalter">
      <button type="button" onClick={schalten} disabled={arbeitet} aria-pressed={an === true}>
        {arbeitet ? "bitte warten …" : an ? "Ausschalten" : "Einschalten"}
      </button>
      {meldung && <span className="sicht"> {meldung}</span>}
    </span>
  );
}

function Ampel({ an }: { an: boolean | null }): JSX.Element {
  if (an === null) return <span className="ampel grau">nicht prüfbar</span>;
  return <span className={an ? "ampel gruen" : "ampel rot"}>{an ? "läuft" : "aus"}</span>;
}

export function SystemSeite(): JSX.Element {
  const [daten, fehler, neu] = useSystem();
  if (fehler) return <p className="fehler">{fehler}</p>;
  if (daten === null) return <p className="laedt">Prüfe Dienste …</p>;
  return (
    <section className="station">
      <h2>System</h2>
      <p className="sicht">
        Welche Dienste der Station laufen und wie frisch die Daten sind. Geprüft
        wird nur, ob der Port antwortet — keine Anmeldung bei IB.{" "}
        <button type="button" onClick={neu}>
          neu prüfen
        </button>
      </p>
      <h3>Dienste</h3>
      <table className="strategie-tabelle">
        <thead>
          <tr>
            <th>Dienst</th>
            <th className="zahl">Port</th>
            <th>Zustand</th>
            <th>Hinweis</th>
          </tr>
        </thead>
        <tbody>
          {daten.dienste.map((d) => (
            <tr key={d.name}>
              <td>{d.name}</td>
              <td className="zahl">{d.port ?? "—"}</td>
              <td>
                <Ampel an={d.erreichbar} />
              </td>
              <td>
                {d.name === "Momentum Lab" ? <MomentumSchalter an={d.erreichbar} neu={neu} /> : (d.hinweis ?? "")}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3>Daten</h3>
      <table className="strategie-tabelle">
        <thead>
          <tr>
            <th>Quelle</th>
            <th>Zuletzt eingelesen</th>
            <th>Daten bis</th>
          </tr>
        </thead>
        <tbody>
          {daten.importe.map((i) => (
            <tr key={i.quelle}>
              <td>{QUELLE[i.quelle] ?? i.quelle}</td>
              <td>{i.zuletzt ? zeitDe(i.zuletzt) : "nie"}</td>
              <td>{i.daten_bis ? datumDe(i.daten_bis) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function zahl(wert: number | null | undefined, stellen = 1): string {
  return wert === null || wert === undefined
    ? "—"
    : wert.toLocaleString("de-DE", { minimumFractionDigits: stellen, maximumFractionDigits: stellen });
}

// AP-14d: Was hat diese Position schon gekostet? Kette im Journal: Rolls,
// bereits realisiertes Ergebnis (Roll-Schritte), Prämie der offenen Legs.
function KettenZelle({ k }: { k?: RollerKette }): JSX.Element {
  if (!k) {
    return (
      <td className="kette" title="Keine eindeutige offene Kette im Journal (Stand des letzten Flex-Imports; heute Eröffnetes fehlt noch)">
        —
      </td>
    );
  }
  return (
    <td className="kette">
      <Link to={`/positionen/${k.chain_id}`} title={k.strategie ?? undefined}>
        {k.anzahl_rolls} {k.anzahl_rolls === 1 ? "Roll" : "Rolls"}
      </Link>
      {k.ketten && k.ketten > 1 ? ` (${k.ketten} Ketten)` : ""}
      {" · "}
      bisher <Betrag wert={k.realisiert_bisher} />
      {k.praemie_offen_eur !== null && (
        <>
          {" · "}
          Prämie <Betrag wert={k.praemie_offen_eur} />
          {k.praemie_aktuell_eur !== null && <> → <Betrag wert={k.praemie_aktuell_eur} /></>}
        </>
      )}
    </td>
  );
}

function verfall(jjjjmmtt: string): string {
  return jjjjmmtt.length === 8
    ? `${jjjjmmtt.slice(6, 8)}.${jjjjmmtt.slice(4, 6)}.${jjjjmmtt.slice(0, 4)}`
    : jjjjmmtt;
}

function StrategieKarte({ s }: { s: RollerStrategie }): JSX.Element {
  const [meldung, setzeMeldung] = useState<string | null>(null);
  const [laeuft, setzeLaeuft] = useState<string | null>(null);
  const [wahl, setzeWahl] = useState<string>(s.vorgaben[0]?.name ?? "");
  const tu = (
    name: "roll-freigabe" | "strategie-pruefen" | "oeffnen" | "kette-aufnehmen" | "auto-an" | "auto-aus",
    parameter: { kette?: string; strategie?: string } = {},
  ) => {
    setzeLaeuft(name + (parameter.kette ?? ""));
    setzeMeldung(name === "strategie-pruefen" ? "Prüfe …" : "Order läuft — der Limit wird nachgezogen, das kann Minuten dauern …");
    sendeRollerBefehl(name, parameter)
      .then((a) => {
        const r = a as { gestartet?: boolean };
        setzeMeldung(name === "strategie-pruefen" ? "Neu geprüft."
          : r && r.gestartet ? "Gestartet — läuft im Hintergrund (das Limit wird nachgezogen, das kann Minuten dauern). Das Ergebnis steht unten bei „Aktion“ und in den Meldungen."
          : `Ergebnis: ${JSON.stringify(a)}`);
      })
      .catch((e) => setzeMeldung(fehlerText(e)))
      .finally(() => setzeLaeuft(null));
  };
  const zahl = (x: number | null | undefined, n = 2) => (x === null || x === undefined ? "—" : x.toFixed(n));
  return (
    <>
      <h3>Strategien (Paper)</h3>
      <p className="sicht">
        {s.paper ? "Paper-Konto verbunden" : "kein Paper-Konto — Orders gesperrt"} · {s.grund}
        {s.daten ? ` · Kurse: ${s.daten.art === "live" ? "live" : s.daten.art === "verzoegert" ? "VERZÖGERT (Balken)" : "unbekannt"}` : ""}
        {s.letzte_pruefung ? ` · geprüft ${zeitDe(s.letzte_pruefung)}` : ""}{" "}
        <button disabled={laeuft !== null} onClick={() => tu("strategie-pruefen")}>Neu prüfen</button>
      </p>
      {s.profil && <p className="sicht">Betriebsprofil: <strong>{s.profil}</strong>{s.profil === "test" ? " — niedrigere Roll-Schwellen, größerer Debit-Rahmen (mehr Rolls zum Testen)" : ""}</p>}
      {s.aktion && (
        <p className={s.aktion.laeuft ? "warnung" : "sicht"}>
          Aktion „{s.aktion.name}“ {s.aktion.laeuft ? `läuft seit ${zeitDe(s.aktion.seit)} …` : `beendet ${s.aktion.ende ? zeitDe(s.aktion.ende) : ""}`}
          {!s.aktion.laeuft && s.aktion.ergebnis ? `: ${JSON.stringify(s.aktion.ergebnis)}` : ""}
        </p>
      )}
      {s.auto && (
        <p className={s.auto.an ? "warnung" : "sicht"}>
          <strong>Automatik: {s.auto.an ? "AN" : "AUS"}</strong> — {s.auto.an
            ? "Der Roller führt zulässige Rolls und Early Exits selbst aus."
            : "Rolls und Early Exits warten auf deine Freigabe."}{" "}
          ({s.auto.heute} von höchstens {s.auto.max_pro_tag} Aktionen heute{s.auto.nur_live ? ", nur mit Live-Daten" : ""}){" "}
          {s.auto.an ? (
            <button onClick={() => tu("auto-aus")} disabled={laeuft !== null}>Not-Aus: Automatik aus</button>
          ) : (
            <button onClick={() => tu("auto-an")} disabled={laeuft !== null || !s.paper}
              title={s.paper ? "Automatik einschalten (nur Paper)" : "Nur gegen das Paper-Konto"}>
              Automatik einschalten
            </button>
          )}
        </p>
      )}
      <p>
        <select value={wahl} onChange={(e) => setzeWahl(e.target.value)}>
          {s.vorgaben.map((v) => (
            <option key={v.name} value={v.name} title={v.text}>{v.name}</option>
          ))}
        </select>{" "}
        <button disabled={laeuft !== null || !s.paper || !wahl} onClick={() => tu("oeffnen", { strategie: wahl })}>
          Eröffnen
        </button>
      </p>
      <p className="hinweis">{s.vorgaben.find((v) => v.name === wahl)?.text}</p>
      {s.ketten.length === 0 ? (
        <p className="hinweis">Keine offene Kette.</p>
      ) : (
        <div className="tabelle-rahmen">
          <table className="strategie-tabelle">
            <thead>
              <tr>
                <th>Kette</th>
                <th>Strategie</th>
                <th>Verfall</th>
                <th className="zahl">DTE</th>
                <th className="zahl">Short/Long</th>
                <th className="zahl">|Δ| Short</th>
                <th className="zahl">Schwelle</th>
                <th className="zahl" title="Summe aller Kredite minus Debits der Kette">Netto</th>
                <th className="zahl">Rolls</th>
                <th className="zahl" title="Rückkauf-Limit des Profit-Targets">PT</th>
                <th>Lage</th>
              </tr>
            </thead>
            <tbody>
              {s.ketten.map((k) => (
                <tr key={k.kette_id} className={k.alarm || k.status === "pruefen" ? "warnung" : undefined}>
                  <td>{k.kette_id}</td>
                  <td>{k.strategie}</td>
                  <td>{verfall(k.aktiv.verfall)}</td>
                  <td className="zahl">{k.dte ?? "—"}</td>
                  <td className="zahl">{k.aktiv.short}/{k.aktiv.long}</td>
                  <td className="zahl">{k.short_delta === null || k.short_delta === undefined ? "—" : Math.abs(k.short_delta).toFixed(3)}</td>
                  <td className="zahl">{zahl(k.schwelle)}</td>
                  <td className="zahl">{zahl(k.netto)}</td>
                  <td className="zahl">{k.rolls}</td>
                  <td className="zahl">{zahl(k.pt_limit)}</td>
                  <td>
                    {k.status === "pruefen" && (
                      <div>
                        <strong>ANGEHALTEN</strong> — {k.warnung}{" "}
                        <button disabled={laeuft !== null || !s.paper}
                          title="Erst den Bestand in der TWS prüfen; der Roller nimmt die Kette nur auf, wenn der Bestand passt"
                          onClick={() => tu("kette-aufnehmen", { kette: k.kette_id })}>
                          Geprüft — wieder aufnehmen
                        </button>
                      </div>
                    )}
                    {k.signal ? <strong>{k.gap ? "GAP · " : ""}ROLL-SIGNAL · </strong> : ""}
                    {k.grund ?? "—"}
                    {k.vorschlag && (k.vorschlag as { art?: string }).art === "schliessen" && (
                      <div>
                        Vorschlag: Kette schließen{(k.vorschlag as { tagesende?: boolean }).tagesende ? " (Tagesende)" : " (Early Exit)"},
                        Rückkauf ca. {zahl((k.vorschlag as { debit?: number }).debit)}{" "}
                        <button disabled={laeuft !== null || !s.paper}
                          onClick={() => tu("roll-freigabe", { kette: k.kette_id })}>
                          Schließen freigeben
                        </button>
                      </div>
                    )}
                    {k.vorschlag && (k.vorschlag as { art?: string }).art !== "schliessen" && (
                      <div>
                        Vorschlag: {verfall(k.vorschlag.neu_verfall)} {k.vorschlag.neu_short}/{k.vorschlag.neu_long}{" "}
                        (+{k.vorschlag.wochen} Wo., {k.vorschlag.verschiebung === 0 ? "horizontal" : `${k.vorschlag.verschiebung} Pkt diagonal`},
                        |Δ| neu {zahl(k.vorschlag.neu_delta === null ? null : Math.abs(k.vorschlag.neu_delta), 3)}), netto{" "}
                        {zahl(k.vorschlag.netto)}, Debit-Rahmen {zahl(k.vorschlag.max_debit)}{" "}
                        <button disabled={laeuft !== null || !s.paper}
                          onClick={() => tu("roll-freigabe", { kette: k.kette_id })}>
                          Roll freigeben
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {meldung && <p className="hinweis">{meldung}</p>}
      {s.tagesprogramm && s.tagesprogramm.strategien.length > 0 && (
        <p className="sicht">
          Tagesprogramm ({s.tagesprogramm.aktiv ? "aktiv, solange die Automatik AN ist" : "wartet auf die Automatik"}):{" "}
          je Börsentag {s.tagesprogramm.ab_min} min nach Handelsbeginn {s.tagesprogramm.strategien.join(", ")};
          Schließen kurz vor Handelsende. Heute eröffnet: {s.tagesprogramm.heute_eroeffnet.length} von{" "}
          {s.tagesprogramm.strategien.length}.
        </p>
      )}
      {s.statistik && Object.keys(s.statistik).length > 0 && (
        <>
          <h3>Auswertung je Strategie</h3>
          <div className="tabelle-rahmen">
            <table className="strategie-tabelle">
              <thead>
                <tr>
                  <th>Strategie</th><th className="zahl">Ketten</th><th className="zahl">offen</th>
                  <th className="zahl">Treffer</th><th className="zahl">Punkte</th><th className="zahl">Ergebnis</th>
                  <th className="zahl">Ø Rolls</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(s.statistik).map(([name, z]) => (
                  <tr key={name}>
                    <td>{name}</td><td className="zahl">{z.n}</td><td className="zahl">{z.offen}</td>
                    <td className="zahl">{z.quote === null ? "—" : `${(z.quote * 100).toFixed(0)} %`}</td>
                    <td className="zahl">{z.punkte.toFixed(2)}</td>
                    <td className="zahl">{z.geld.toFixed(2)} {z.waehrung}</td>
                    <td className="zahl">{z.rolls_schnitt === null ? "—" : z.rolls_schnitt.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      {s.abgeschlossen && s.abgeschlossen.length > 0 && (
        <details>
          <summary>Abgeschlossene Ketten ({s.abgeschlossen.length} zuletzt)</summary>
          <div className="tabelle-rahmen">
            <table className="strategie-tabelle">
              <thead>
                <tr>
                  <th>Kette</th><th>Strategie</th><th>Eröffnet</th><th>Geschlossen</th><th className="zahl">Kredit</th>
                  <th className="zahl">Rolls</th><th>Schluss</th><th className="zahl">Ergebnis</th>
                </tr>
              </thead>
              <tbody>
                {s.abgeschlossen.map((a) => (
                  <tr key={a.kette_id}>
                    <td>{a.kette_id}</td><td>{a.strategie}</td>
                    <td>{a.angelegt ? zeitDe(a.angelegt) : "—"}</td><td>{a.geschlossen ? zeitDe(a.geschlossen) : "—"}</td>
                    <td className="zahl">{a.erstkredit === null ? "—" : a.erstkredit.toFixed(2)}</td>
                    <td className="zahl">{a.rolls}</td><td>{a.schluss ?? "—"}</td>
                    <td className="zahl">{a.punkte.toFixed(2)} Pkt = {a.geld.toFixed(2)} {a.waehrung}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
      {s.meldungen.length > 0 && (
        <details>
          <summary>Meldungen ({s.meldungen.length})</summary>
          <ul>{[...s.meldungen].reverse().map((m, i) => <li key={i}>{m}</li>)}</ul>
        </details>
      )}
    </>
  );
}

export function RollerSeite(): JSX.Element {
  const [daten, setzeDaten] = useState<RollerAntwort | null>(null);
  const [fehler, setzeFehler] = useState<string | null>(null);
  useEffect(() => {
    let aktiv = true;
    const laden = () =>
      holeRoller()
        .then((d) => aktiv && setzeDaten(d))
        .catch((e) => aktiv && setzeFehler(fehlerText(e)));
    laden();
    const takt = window.setInterval(laden, 15000);
    return () => {
      aktiv = false;
      window.clearInterval(takt);
    };
  }, []);

  if (fehler) return <p className="fehler">{fehler}</p>;
  if (daten === null) return <p className="laedt">Frage den Roller …</p>;
  if (!daten.erreichbar || daten.status === null) {
    return (
      <section className="station">
        <h2>Options Roller</h2>
        <p className="hinweis">
          Der Roller-Dienst läuft nicht. Starten im Ordner des Rollers mit{" "}
          <code>.venv\Scripts\python -m roller.dienst</code> (nur lesend; E-Mails
          mit <code>--mails</code>). Diese Seite aktualisiert sich selbst.
        </p>
      </section>
    );
  }
  const s = daten.status;
  const alter = Math.round((Date.now() - new Date(s.herzschlag).getTime()) / 1000);
  return (
    <section className="station">
      <h2>Options Roller</h2>
      <p className="sicht">
        Stufe {s.stufe}: {s.orders.freigegeben ? s.orders.modus : "nur lesen — der Dienst setzt keine Orders ab"}.{" "}
        <span className={s.ib.verbunden ? "ampel gruen" : "ampel rot"}>
          {s.ib.verbunden ? `IB verbunden (Port ${s.ib.port})` : "IB nicht verbunden"}
        </span>{" "}
        · {s.positionen.spreads} Spreads, {s.positionen.einzel} Einzelpositionen · Scan{" "}
        {s.scanner.laeufe}× (
        {s.scanner.letzter_lauf ? zeitDe(s.scanner.letzter_lauf) : "noch keiner"}, alle{" "}
        {s.scanner.intervall_s ?? "—"} s) · Symbole: {s.scanner.symbole.join(", ") || "—"} ·
        Herzschlag vor {alter} s
      </p>

      {s.strategie && <StrategieKarte s={s.strategie} />}

      <h3>Breaches ({s.breaches.length})</h3>
      {s.breaches.length === 0 ? (
        <p className="hinweis">Kein Short-Strike hat seinen Danger-Strike überschritten.</p>
      ) : (
        <div className="tabelle-rahmen">
          <table className="strategie-tabelle">
            <thead>
              <tr>
                <th>Basiswert</th>
                <th>Verfall</th>
                <th>Seite</th>
                <th className="zahl">DTE</th>
                <th className="zahl">Short</th>
                <th className="zahl">Danger</th>
                <th className="zahl" title="Abstand Basiswert zu Short in Indexpunkten; negativ = im Geld">
                  Puffer
                </th>
                <th className="zahl">|Δ| Short</th>
                <th className="zahl" title="Theoretischer Wert des Rolls in Indexpunkten">Roll Theo</th>
                <th className="zahl" title="Positiv = Markt verlangt mehr als das Modell (teuer)">Edge</th>
                <th>Bewertung</th>
                <th title="Geschichte dieser Kette im Journal: Rolls, bisher realisiert (EUR), Prämie bei Eröffnung → aktuell">
                  Kette im Journal
                </th>
              </tr>
            </thead>
            <tbody>
              {s.breaches.map((b) => (
                <tr key={b.position_key}>
                  <td>{b.symbol}</td>
                  <td>{verfall(b.expiration)}</td>
                  <td>{b.right === "P" ? "Put" : "Call"}</td>
                  <td className="zahl">{b.dte}</td>
                  <td className="zahl">{zahl(b.short_strike, 0)}</td>
                  <td className="zahl">{zahl(b.danger_strike, 1)}</td>
                  <td className="zahl">{zahl(b.puffer, 0)}</td>
                  <td className="zahl">{zahl(b.short_delta, 2)}</td>
                  <td className="zahl">{zahl(b.edge?.theo_roll)}</td>
                  <td className="zahl">{zahl(b.edge?.edge_abs, 2)}</td>
                  <td>{b.edge ? `${b.edge.verdict ?? "—"} (${b.edge.data_quality ?? "—"})` : "—"}</td>
                  <KettenZelle k={b.kette} />
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h3>Offene Spreads ({s.spreads.length})</h3>
      <div className="tabelle-rahmen">
        <table className="strategie-tabelle">
          <thead>
            <tr>
              <th>Basiswert</th>
              <th>Typ</th>
              <th>Verfall</th>
              <th className="zahl">Menge</th>
              <th className="zahl">Short / Long</th>
              <th className="zahl">|Δ| Short</th>
              <th className="zahl">Basiswert</th>
              <th>Kette im Journal</th>
            </tr>
          </thead>
          <tbody>
            {s.spreads.map((p) => (
              <tr key={p.key}>
                <td>{p.symbol}</td>
                <td>{p.typ}</td>
                <td>{verfall(p.expiration)}</td>
                <td className="zahl">{p.menge}</td>
                <td className="zahl">
                  {zahl(p.short, 0)} / {zahl(p.long, 0)}
                </td>
                <td className="zahl">{zahl(p.short_delta, 2)}</td>
                <td className="zahl">{zahl(p.underlying, 1)}</td>
                <KettenZelle k={p.kette} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>Stufen</h3>
      <ol className="stufen">
        <li><strong>R1 Inbetriebnahme</strong> — erledigt.</li>
        <li><strong>R2 Sichtbar</strong> — diese Seite, Dienst ohne Fenster.</li>
        <li><strong>R3 Vorschlag und Freigabe per Klick</strong> — zuerst im Paper-Konto.</li>
        <li><strong>R4 Schattenmodus</strong> — entscheidet automatisch, schickt nichts ab.</li>
        <li><strong>R5 Automatik mit Leitplanken</strong> — Rolls je Kette und Roll-Verlust begrenzt, Tageslimits, Not-Aus.</li>
      </ol>
      <details>
        <summary>Protokoll des Dienstes</summary>
        <pre className="protokoll">{s.log.slice(-40).join("\n")}</pre>
      </details>
    </section>
  );
}

export function MomentumSeite(): JSX.Element {
  const [daten, , neu] = useSystem();
  const lab = daten?.dienste.find((d) => d.name === "Momentum Lab");
  if (!daten) return <p className="laedt">Prüfe Momentum Lab …</p>;
  if (!lab?.erreichbar) {
    return (
      <section className="station">
        <h2>Momentum Lab</h2>
        <p className="hinweis">
          Momentum Lab läuft gerade nicht.
        </p>
        <p>
          <MomentumSchalter an={false} neu={neu} />
        </p>
      </section>
    );
  }
  return (
    <section className="station eingebettet">
      <p className="sicht">
        Momentum Lab läuft als eigener Dienst und ist hier eingebettet.{" "}
        <a href="http://127.0.0.1:8501" target="_blank" rel="noreferrer">
          In eigenem Fenster öffnen
        </a>{" "}
        <MomentumSchalter an={true} neu={neu} />
      </p>
      <iframe title="Momentum Lab" src="http://127.0.0.1:8501" className="einbettung" />
    </section>
  );
}

function statusKlasse(status: string | null): string {
  const s = (status ?? "").toLowerCase();
  if (s.includes("retired") || s.includes("failed") || s.includes("nicht bestanden")) return "ampel rot";
  if (s.includes("blocked") || s.includes("pause")) return "ampel grau";
  if (s.includes("alle gates")) return "ampel gruen";
  return "ampel grau";
}

export function BreakoutSeite(): JSX.Element {
  const [daten, setzeDaten] = useState<BreakoutStand | null>(null);
  const [fehler, setzeFehler] = useState<string | null>(null);
  useEffect(() => {
    holeBreakout()
      .then(setzeDaten)
      .catch((e) => setzeFehler(fehlerText(e)));
  }, []);
  if (fehler) return <p className="fehler">{fehler}</p>;
  if (daten === null) return <p className="laedt">Lese BO Research Suite …</p>;
  if (!daten.gefunden) {
    return (
      <section className="station">
        <h2>Breakout Research</h2>
        <p className="hinweis">
          Die BO Research Suite wurde nicht gefunden. Erwartet in
          C:\10_Coding\BO Research Suite (anderer Ort: Umgebungsvariable BO_ORDNER).
        </p>
      </section>
    );
  }
  return (
    <section className="station">
      <h2>Breakout Research</h2>
      <p className="sicht">
        Forschungsstand der BO Research Suite, nur lesend (Stand {daten.stand ?? "unbekannt"}). Das
        Projekt läuft nach eigenen Regeln: Validation und Holdout bleiben versiegelt, je Hypothese
        gibt es genau einen Discovery-Lauf. Ein sauber laufender Test ist kein Beleg für einen
        Handelsvorteil.
      </p>
      {daten.ziel && <p className="ziel">{daten.ziel}</p>}

      <h3>Discovery-Ergebnisse ({daten.ergebnisse.length})</h3>
      <div className="tabelle-rahmen">
        <table className="strategie-tabelle">
          <thead>
            <tr>
              <th>Hypothese</th>
              <th>Status</th>
              <th className="zahl">Sitzungen</th>
              <th className="zahl" title="Mittel je Sitzung in SPX-Punkten bei 0,5 Punkten Kosten">
                Ø Punkte (0,5 Kosten)
              </th>
              <th className="zahl" title="Untere 5-%-Grenze des Bootstrap, primäre Kennzahl; über 0 = Voraussetzung">
                Bootstrap p05
              </th>
              <th className="zahl" title="Bestandene Gates von allen">Gates</th>
            </tr>
          </thead>
          <tbody>
            {daten.ergebnisse.map((e) => {
              const ok = Object.values(e.gates).filter(Boolean).length;
              return (
                <tr key={e.id}>
                  <td>{e.id}</td>
                  <td>
                    <span className={statusKlasse(e.status)}>{e.status ?? "—"}</span>
                  </td>
                  <td className="zahl">{e.sitzungen ?? "—"}</td>
                  <td className="zahl">{zahl(e.mittel_punkte_05, 2)}</td>
                  <td className="zahl">{zahl(e.bootstrap_p05, 2)}</td>
                  <td className="zahl">
                    {Object.keys(e.gates).length ? `${ok} / ${Object.keys(e.gates).length}` : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <h3>Hypothesenregister ({daten.hypothesen.length})</h3>
      <div className="tabelle-rahmen">
        <table className="strategie-tabelle">
          <thead>
            <tr>
              <th>ID</th>
              <th>Frage</th>
              <th>Stufe</th>
              <th>Status</th>
              <th>Entscheidung</th>
            </tr>
          </thead>
          <tbody>
            {daten.hypothesen.map((h) => (
              <tr key={h.id}>
                <td>{h.id}</td>
                <td title={h.evidenz ?? undefined}>{h.frage ?? "—"}</td>
                <td>{h.stufe ?? "—"}</td>
                <td>
                  <span className={statusKlasse(h.status)}>{h.status ?? "—"}</span>
                </td>
                <td>{h.entscheidung ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
