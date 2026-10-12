import { useEffect, useState } from "react";
import { fehlerText, holeSystem } from "./api";
import type { System } from "./api";
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

export function RollerSeite(): JSX.Element {
  const [daten] = useSystem();
  const tws = daten?.dienste.filter((d) => d.name.startsWith("TWS") || d.name.startsWith("IB"));
  return (
    <section className="station">
      <h2>Options Roller</h2>
      <p className="sicht">
        Hier entsteht die Bedienung des Rollers: Positionen mit Danger-Strikes,
        Breaches, Roll-Edge und Rollvorschläge zur Freigabe. Der Roller läuft
        dafür als eigener Dienst ohne Fenster.
      </p>
      <ol className="stufen">
        <li>
          <strong>R1 Inbetriebnahme</strong> — erledigt am 12.10.2026: TWS API,
          Fehlermeldungen der neuen API, Order-Sperre, Lesetest gegen TWS.
        </li>
        <li>
          <strong>R2 Sichtbar</strong> — Status, Breaches und Roll-Edge auf
          dieser Seite.
        </li>
        <li>
          <strong>R3 Vorschlag und Freigabe per Klick</strong> — zuerst im
          Paper-Konto.
        </li>
        <li>
          <strong>R4 Schattenmodus</strong> — entscheidet automatisch, schickt
          nichts ab.
        </li>
        <li>
          <strong>R5 Automatik mit Leitplanken</strong> — Rolls je Kette und
          Roll-Verlust begrenzt, Tageslimits, Not-Aus.
        </li>
      </ol>
      {tws && (
        <p className="sicht">
          IB-Verbindung:{" "}
          {tws
            .filter((d) => d.erreichbar)
            .map((d) => d.name)
            .join(", ") || "keine TWS und kein Gateway erreichbar"}
        </p>
      )}
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
