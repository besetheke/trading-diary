import { useEffect, useState } from "react";
import { fehlerText, holeRoller, holeSystem } from "./api";
import type { RollerAntwort, System } from "./api";
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
              <td>{d.hinweis ?? ""}</td>
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

function verfall(jjjjmmtt: string): string {
  return jjjjmmtt.length === 8
    ? `${jjjjmmtt.slice(6, 8)}.${jjjjmmtt.slice(4, 6)}.${jjjjmmtt.slice(0, 4)}`
    : jjjjmmtt;
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
        Stufe {s.stufe}: nur lesen — der Dienst setzt keine Orders ab.{" "}
        <span className={s.ib.verbunden ? "ampel gruen" : "ampel rot"}>
          {s.ib.verbunden ? `IB verbunden (Port ${s.ib.port})` : "IB nicht verbunden"}
        </span>{" "}
        · {s.positionen.spreads} Spreads, {s.positionen.einzel} Einzelpositionen · Scan{" "}
        {s.scanner.laeufe}× (
        {s.scanner.letzter_lauf ? zeitDe(s.scanner.letzter_lauf) : "noch keiner"}, alle{" "}
        {s.scanner.intervall_s ?? "—"} s) · Symbole: {s.scanner.symbole.join(", ") || "—"} ·
        Herzschlag vor {alter} s
      </p>

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
  const [daten] = useSystem();
  const lab = daten?.dienste.find((d) => d.name === "Momentum Lab");
  if (!daten) return <p className="laedt">Prüfe Momentum Lab …</p>;
  if (!lab?.erreichbar) {
    return (
      <section className="station">
        <h2>Momentum Lab</h2>
        <p className="hinweis">
          Momentum Lab läuft gerade nicht. {lab?.hinweis ?? ""} — danach diese
          Seite neu laden.
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
        </a>
      </p>
      <iframe title="Momentum Lab" src="http://127.0.0.1:8501" className="einbettung" />
    </section>
  );
}

export function BreakoutSeite(): JSX.Element {
  return (
    <section className="station">
      <h2>Breakout Research</h2>
      <p className="sicht">
        Platz für die Breakout-Forschung (Identifizieren und Testen von
        BO-Strategien). Wird eingebunden, sobald das Projekt unter
        C:\10_Coding liegt.
      </p>
    </section>
  );
}
