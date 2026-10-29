// Visualisierung der Roller-Ketten und ihrer Rollparameter (Nutzerwunsch 25.10.2026).
// Je Kette eine Karte mit vier Bildern, alles reines SVG aus den Werten des Roller-Status (nichts wird gerechnet,
// was der Roller nicht schon liefert):
//   1. Strike-Leiter   — Spot, Short/Long der Kette, vorgeschlagene neue Position, Abstand in Punkten und Prozent
//   2. Rollregel       — Treppe der |Δ|-Schwellen nach Restlaufzeit, Gap-Linie, Ziel-Δ und der Punkt der Kette
//   3. Kostenbremse    — Netto der Kette gegen die Grenze (Anteil × Breite)
//   4. Kettenverlauf   — Short-Strike über Eröffnung und Rolls, Netto je Schritt

import { useEffect, useState } from 'react'
import type { RollerKetteStand, RollerRegeln, RollerStrategie } from './api'

const GRUEN = '#0f5d50'
const AMBER = '#b7791f'
const ROT = '#b42318'
const GRAU = '#6f6a60'
const HELL = '#d8d5cf'

function n(wert: number | null | undefined, stellen = 2): string {
  return wert === null || wert === undefined
    ? '—'
    : wert.toLocaleString('de-DE', { minimumFractionDigits: stellen, maximumFractionDigits: stellen })
}

function datum(jjjjmmtt: string): string {
  return jjjjmmtt.length === 8 ? `${jjjjmmtt.slice(6, 8)}.${jjjjmmtt.slice(4, 6)}.` : jjjjmmtt
}

function seiteVon(k: RollerKetteStand, regeln?: RollerRegeln): 'BPS' | 'BCS' {
  if (regeln?.seite === 'BPS' || regeln?.seite === 'BCS') return regeln.seite
  return k.strategie.includes('BCS') ? 'BCS' : 'BPS'
}

// ------------------------------------------------------------------------------------------------ 1. Strike-Leiter

export function StrikeLeiter(props: { kette: RollerKetteStand; regeln?: RollerRegeln }): JSX.Element {
  const { kette: k, regeln } = props
  const seite = seiteVon(k, regeln)
  const neu = k.vorschlag && 'neu_short' in k.vorschlag ? k.vorschlag : null
  const werte = [k.aktiv.short, k.aktiv.long, k.spot ?? null, neu?.neu_short ?? null, neu?.neu_long ?? null].filter(
    (w): w is number => typeof w === 'number',
  )
  const lo = Math.min(...werte)
  const hi = Math.max(...werte)
  const rand = Math.max((hi - lo) * 0.18, (regeln?.breite ?? 10) * 0.6)
  const von = lo - rand
  const bis = hi + rand
  const B = 560
  const x = (w: number) => 20 + ((w - von) / (bis - von)) * (B - 40)

  const spot = k.spot ?? null
  const abstand = spot === null ? null : seite === 'BPS' ? spot - k.aktiv.short : k.aktiv.short - spot
  const imGeld = abstand !== null && abstand < 0
  const prozent = spot !== null && spot !== 0 && abstand !== null ? (abstand / spot) * 100 : null
  const farbe = imGeld ? ROT : k.signal ? AMBER : GRUEN

  return (
    <figure className="kk-bild">
      <figcaption>
        Strike-Leiter · {seite === 'BPS' ? 'Put-Spread (Verlust bei fallendem Kurs)' : 'Call-Spread (Verlust bei steigendem Kurs)'}
        {abstand !== null && (
          <>
            {' · '}
            <strong style={{ color: imGeld ? ROT : undefined }}>
              {imGeld ? 'Short im Geld' : 'Puffer'} {n(Math.abs(abstand), 0)} Pkt{prozent !== null ? ` (${n(Math.abs(prozent), 1)} %)` : ''}
            </strong>
          </>
        )}
      </figcaption>
      <svg viewBox={`0 0 ${B} 120`} role="img" aria-label="Strike-Leiter der Kette">
        <line x1={20} x2={B - 20} y1={52} y2={52} stroke={HELL} strokeWidth={2} />
        {/* aktuelle Position: Band zwischen Short und Long */}
        <rect
          x={Math.min(x(k.aktiv.short), x(k.aktiv.long))}
          y={38}
          width={Math.abs(x(k.aktiv.short) - x(k.aktiv.long))}
          height={28}
          fill={farbe}
          opacity={0.18}
          stroke={farbe}
        />
        <line x1={x(k.aktiv.short)} x2={x(k.aktiv.short)} y1={30} y2={74} stroke={farbe} strokeWidth={3} />
        <line x1={x(k.aktiv.long)} x2={x(k.aktiv.long)} y1={34} y2={70} stroke={farbe} strokeWidth={1.5} />
        <text x={x(k.aktiv.short)} y={24} textAnchor="middle" fontSize={11} fill={farbe}>
          Short {k.aktiv.short}
        </text>
        <text x={x(k.aktiv.long)} y={86} textAnchor="middle" fontSize={11} fill={GRAU}>
          Long {k.aktiv.long}
        </text>
        {/* vorgeschlagene neue Position */}
        {neu && (
          <>
            <rect
              x={Math.min(x(neu.neu_short), x(neu.neu_long))}
              y={96}
              width={Math.abs(x(neu.neu_short) - x(neu.neu_long))}
              height={10}
              fill="none"
              stroke={GRUEN}
              strokeDasharray="4 3"
            />
            <text x={x(neu.neu_short)} y={116} textAnchor="middle" fontSize={10} fill={GRUEN}>
              Roll → {neu.neu_short}/{neu.neu_long}
            </text>
          </>
        )}
        {/* Spot */}
        {spot !== null && (
          <>
            <line x1={x(spot)} x2={x(spot)} y1={8} y2={96} stroke={GRAU} strokeDasharray="3 3" />
            <polygon points={`${x(spot) - 5},4 ${x(spot) + 5},4 ${x(spot)},12`} fill={GRAU} />
            <text x={x(spot)} y={106} textAnchor="middle" fontSize={11} fill={GRAU} style={{ display: neu ? 'none' : undefined }}>
              Spot {n(spot, 0)}
            </text>
            {neu && (
              <text x={x(spot) + 8} y={14} fontSize={11} fill={GRAU}>
                Spot {n(spot, 0)}
              </text>
            )}
          </>
        )}
      </svg>
    </figure>
  )
}

// ------------------------------------------------------------------------------------------------ 2. Rollregel

export function RollRegel(props: { kette: RollerKetteStand; regeln?: RollerRegeln }): JSX.Element | null {
  const { kette: k, regeln } = props
  if (!regeln || regeln.staffel.length === 0) return null
  const staffel = [...regeln.staffel].sort((a, b) => a[0] - b[0])
  const maxDte = staffel[staffel.length - 1][0]
  const xMax = maxDte + Math.max(7, Math.round(maxDte * 0.25))
  const yMax = Math.max(0.6, ...staffel.map(([, d]) => d + regeln.gap_aufschlag + 0.02))
  const B = 560
  const H = 190
  const links = 44
  const unten = 156
  const oben = 14
  const x = (dte: number) => links + (dte / xMax) * (B - links - 16)
  const y = (d: number) => unten - (d / yMax) * (unten - oben)

  // Treppe: für Restlaufzeit <= Grenze gilt die Schwelle der ersten passenden Stufe.
  const stufen = staffel.map(([grenze, d], i) => ({ von: i === 0 ? 0 : staffel[i - 1][0], bis: grenze, d }))
  const treppe = (zuschlag: number) =>
    stufen.map((s) => `${x(s.von)},${y(s.d + zuschlag)} ${x(s.bis)},${y(s.d + zuschlag)}`).join(' ')

  const delta = k.short_delta === null || k.short_delta === undefined ? null : Math.abs(k.short_delta)
  const dte = k.dte ?? null
  const schwelle = k.schwelle ?? null
  const farbe = delta === null || schwelle === null ? GRAU : delta > schwelle ? ROT : delta >= 0.8 * schwelle ? AMBER : GRUEN
  const punktX = dte === null ? null : x(Math.min(dte, xMax))

  return (
    <figure className="kk-bild">
      <figcaption>
        Rollregel · rollt, sobald |Δ| des Short über die Stufe der Restlaufzeit steigt (Gap ab +{n(regeln.gap_aufschlag)}) · neue Position Ziel-Δ{' '}
        {n(regeln.ziel_delta)}, bis {regeln.roll_wochen_max} Wochen weiter, Short höchstens {n(regeln.max_verschiebung, 0)} Pkt verschoben
      </figcaption>
      <svg viewBox={`0 0 ${B} ${H}`} role="img" aria-label="Rollregel: Delta-Schwelle nach Restlaufzeit">
        {/* Raster und Achsen */}
        {[0, 0.2, 0.4, 0.6].filter((d) => d <= yMax).map((d) => (
          <g key={d}>
            <line x1={links} x2={B - 16} y1={y(d)} y2={y(d)} stroke={HELL} strokeWidth={d === 0 ? 1.5 : 0.7} />
            <text x={links - 6} y={y(d) + 4} textAnchor="end" fontSize={10} fill={GRAU}>
              {n(d)}
            </text>
          </g>
        ))}
        {Array.from({ length: Math.floor(xMax / 7) + 1 }, (_, i) => i * 7).map((d) => (
          <text key={d} x={x(d)} y={unten + 14} textAnchor="middle" fontSize={10} fill={GRAU}>
            {d}
          </text>
        ))}
        <text x={(links + B - 16) / 2} y={H - 4} textAnchor="middle" fontSize={10} fill={GRAU}>
          Restlaufzeit in Tagen
        </text>
        {/* Bereich ohne Roll (zu weit vom Verfall) */}
        <rect x={x(maxDte)} y={oben} width={x(xMax) - x(maxDte)} height={unten - oben} fill={HELL} opacity={0.35} />
        <text x={(x(maxDte) + x(xMax)) / 2} y={oben + 14} textAnchor="middle" fontSize={10} fill={GRAU}>
          noch kein Roll
        </text>
        {/* Bereich über der Schwelle = Roll-Signal */}
        <polyline points={treppe(0)} fill="none" stroke={GRUEN} strokeWidth={2.5} />
        <polyline points={treppe(regeln.gap_aufschlag)} fill="none" stroke={ROT} strokeWidth={1.2} strokeDasharray="5 3" />
        <text x={x(1)} y={y(stufen[0].d + regeln.gap_aufschlag) - 4} fontSize={10} fill={ROT}>
          Gap
        </text>
        <text x={x(1)} y={y(stufen[0].d) + 13} fontSize={10} fill={GRUEN}>
          Roll-Schwelle
        </text>
        {/* Ziel-Delta der neuen Position */}
        <line x1={links} x2={x(xMax)} y1={y(regeln.ziel_delta)} y2={y(regeln.ziel_delta)} stroke={GRAU} strokeDasharray="2 3" />
        <text x={B - 18} y={y(regeln.ziel_delta) - 4} textAnchor="end" fontSize={10} fill={GRAU}>
          Ziel-Δ {n(regeln.ziel_delta)}
        </text>
        {/* aktuelle Kette */}
        {punktX !== null && delta !== null && (
          <>
            <circle cx={punktX} cy={y(Math.min(delta, yMax))} r={6} fill={farbe} stroke="#fff" strokeWidth={1.5} />
            <text x={punktX + 9} y={y(Math.min(delta, yMax)) - 6} fontSize={11} fill={farbe}>
              |Δ| {n(delta, 3)} bei {dte} Tagen
            </text>
          </>
        )}
      </svg>
      {delta === null && <p className="sicht">Noch kein Delta geprüft — der Punkt der Kette erscheint nach der nächsten Prüfung.</p>}
    </figure>
  )
}

// ------------------------------------------------------------------------------------------------ 3. Kostenbremse

export function Kostenbremse(props: { kette: RollerKetteStand; regeln?: RollerRegeln }): JSX.Element | null {
  const { kette: k, regeln } = props
  if (!regeln || regeln.max_kettenverlust_anteil === null || regeln.max_kettenverlust_anteil === undefined) return null
  const grenze = regeln.max_kettenverlust_anteil * regeln.breite
  const verlust = Math.max(0, -k.netto)
  const anteil = grenze > 0 ? verlust / grenze : 0
  const fuellstand = Math.min(1, anteil)
  const farbe = anteil >= 1 ? ROT : anteil >= 0.75 ? AMBER : GRUEN
  return (
    <figure className="kk-bild">
      <figcaption>
        Kostenbremse · Netto der Kette {n(k.netto)} gegen Grenze −{n(grenze)} ({n(regeln.max_kettenverlust_anteil * 100, 0)} % der Breite{' '}
        {n(regeln.breite, 0)})
      </figcaption>
      <svg viewBox="0 0 560 34" role="img" aria-label={`Kostenbremse: ${n(anteil * 100, 0)} Prozent der Grenze`}>
        <rect x={20} y={8} width={520} height={16} fill={HELL} opacity={0.5} rx={3} />
        <rect x={20} y={8} width={520 * fuellstand} height={16} fill={farbe} rx={3} />
        <text x={24} y={20} fontSize={11} fill={fuellstand > 0.15 ? '#fff' : GRAU}>
          {n(anteil * 100, 0)} % der Grenze
        </text>
        {anteil > 1 && <polygon points="540,4 551,16 540,28" fill={ROT} />}
      </svg>
      {anteil >= 1 && (
        <p className="warnung">
          {anteil > 1 ? 'Grenze überschritten' : 'Grenze erreicht'}: die Automatik rollt nicht weiter, du entscheidest über Weiterrollen oder Schließen.
        </p>
      )}
    </figure>
  )
}

// ------------------------------------------------------------------------------------------------ 4. Kettenverlauf

export function Kettenverlauf(props: { kette: RollerKetteStand }): JSX.Element | null {
  const { kette: k } = props
  const schritte = k.verlauf ?? []
  const rolls = schritte.filter((b) => b.art === 'roll')
  if (schritte.length === 0) return null
  const aktuell = { verfall: k.aktiv.verfall, short: k.aktiv.short, long: k.aktiv.long }
  // Position nach dem i-ten Roll = „von“ des nächsten Rolls, nach dem letzten die aktuelle.
  const positionen = [rolls[0]?.von ?? aktuell, ...rolls.map((_, i) => rolls[i + 1]?.von ?? aktuell)]
  const zeiten = [schritte.find((b) => b.art === 'eroeffnung')?.zeit ?? null, ...rolls.map((r) => r.zeit ?? null)]
  const netto = [schritte.find((b) => b.art === 'eroeffnung')?.netto ?? null, ...rolls.map((r) => r.netto ?? null)]
  const shorts = positionen.map((p) => p.short)
  const lo = Math.min(...shorts, k.spot ?? Infinity)
  const hi = Math.max(...shorts, k.spot ?? -Infinity)
  const rand = Math.max((hi - lo) * 0.2, 5)
  const B = Math.max(560, positionen.length * 120)
  const H = 150
  const x = (i: number) => (positionen.length === 1 ? B / 2 : 40 + (i / (positionen.length - 1)) * (B - 80))
  const y = (w: number) => 20 + (1 - (w - (lo - rand)) / (hi + rand - (lo - rand))) * 80

  let kumuliert = 0
  const kumuliertJeSchritt = netto.map((w) => (kumuliert += w ?? 0))

  return (
    <figure className="kk-bild">
      <figcaption>
        Kettenverlauf · Short-Strike je Schritt ({rolls.length} {rolls.length === 1 ? 'Roll' : 'Rolls'}), darunter Netto des Schritts und
        kumuliert
      </figcaption>
      <svg viewBox={`0 0 ${B} ${H}`} style={{ minWidth: `${B}px` }} role="img" aria-label="Short-Strike über die Rolls der Kette">
        {k.spot !== null && k.spot !== undefined && (
          <>
            <line x1={20} x2={B - 20} y1={y(k.spot)} y2={y(k.spot)} stroke={GRAU} strokeDasharray="3 3" />
            <text x={B - 22} y={y(k.spot) - 4} textAnchor="end" fontSize={10} fill={GRAU}>
              Spot jetzt {n(k.spot, 0)}
            </text>
          </>
        )}
        <polyline points={positionen.map((p, i) => `${x(i)},${y(p.short)}`).join(' ')} fill="none" stroke={GRUEN} strokeWidth={2} />
        {positionen.map((p, i) => (
          <g key={i}>
            <circle cx={x(i)} cy={y(p.short)} r={5} fill={i === 0 ? '#fff' : GRUEN} stroke={GRUEN} strokeWidth={2} />
            <text x={x(i)} y={y(p.short) - 9} textAnchor="middle" fontSize={11} fill={GRUEN}>
              {p.short}
            </text>
            <text x={x(i)} y={118} textAnchor="middle" fontSize={10} fill={GRAU}>
              {i === 0 ? 'Eröffnung' : `Roll ${i}`} · {datum(p.verfall)}
            </text>
            <text x={x(i)} y={131} textAnchor="middle" fontSize={10} fill={(netto[i] ?? 0) < 0 ? ROT : GRAU}>
              {n(netto[i])}
            </text>
            <text x={x(i)} y={144} textAnchor="middle" fontSize={10} fontWeight={600} fill={kumuliertJeSchritt[i] < 0 ? ROT : GRUEN}>
              Σ {n(kumuliertJeSchritt[i])}
            </text>
            {zeiten[i] && (
              <title>{`${i === 0 ? 'Eröffnung' : `Roll ${i}`}: ${zeiten[i]?.replace('T', ' ').slice(0, 16)}`}</title>
            )}
          </g>
        ))}
      </svg>
    </figure>
  )
}

// ------------------------------------------------------------------------------------------------ Karten

function kostenAnteil(k: RollerKetteStand, regeln?: RollerRegeln): number | null {
  if (!regeln || regeln.max_kettenverlust_anteil === null || regeln.max_kettenverlust_anteil === undefined) return null
  const grenze = regeln.max_kettenverlust_anteil * regeln.breite
  return grenze > 0 ? Math.max(0, -k.netto) / grenze : null
}

function hatHandlungsbedarf(k: RollerKetteStand, regeln?: RollerRegeln): boolean {
  return Boolean(k.alarm || k.signal || k.gap || k.status === 'pruefen' || k.vorschlag) || (kostenAnteil(k, regeln) ?? 0) >= 0.75
}

function KettenkarteAufklappbar({ k, regeln }: { k: RollerKetteStand; regeln?: RollerRegeln }): JSX.Element {
  const kritisch = hatHandlungsbedarf(k, regeln)
  const [offen, setOffen] = useState(true)
  const bremse = kostenAnteil(k, regeln)
  const delta = k.short_delta === null || k.short_delta === undefined ? null : Math.abs(k.short_delta)
  useEffect(() => {
    if (kritisch) setOffen(true)
  }, [kritisch])
  return (
    <details className={`kettenkarte${kritisch ? ' bedarf' : ''}`} open={offen} onToggle={(e) => setOffen(e.currentTarget.open)}>
      <summary>
        <span className={`kk-zustand ${kritisch ? 'rot' : 'gruen'}`}>{kritisch ? 'Handlungsbedarf' : 'ruhig'}</span>{' '}
        <strong>{k.kette_id}</strong> · {k.strategie} · Verfall {datum(k.aktiv.verfall)} · {k.dte ?? '—'} DTE
        <span className="kk-kennzahlen">
          |Δ| {delta === null ? '—' : n(delta, 3)} / {n(k.schwelle)} · Netto {n(k.netto)}
          {bremse !== null ? ` · Bremse ${n(bremse * 100, 0)} %` : ''} · {k.rolls} {k.rolls === 1 ? 'Roll' : 'Rolls'}
          {k.status === 'pruefen' ? ' · ANGEHALTEN' : ''}
        </span>
      </summary>
      <div className="kettenkarte-inhalt">
        {!regeln && <p className="sicht">Rollparameter dieser Strategie sind im Status nicht enthalten (Roller aktualisieren).</p>}
        <div className="kk-raster">
          <StrikeLeiter kette={k} regeln={regeln} />
          <RollRegel kette={k} regeln={regeln} />
          <Kostenbremse kette={k} regeln={regeln} />
          <Kettenverlauf kette={k} />
        </div>
        {k.grund && <p className="sicht">{k.grund}</p>}
      </div>
    </details>
  )
}

export default function Kettenkarten(props: { strategie: RollerStrategie }): JSX.Element | null {
  const { strategie: s } = props
  if (s.ketten.length === 0) return null
  const regelnJe = new Map(s.vorgaben.map((v) => [v.name, v.regeln]))
  const geordnet = [...s.ketten].sort((a, b) => {
    const bedarf = Number(hatHandlungsbedarf(b, regelnJe.get(b.strategie))) - Number(hatHandlungsbedarf(a, regelnJe.get(a.strategie)))
    return bedarf || (a.dte ?? 1e9) - (b.dte ?? 1e9) || a.kette_id.localeCompare(b.kette_id, 'de', { numeric: true })
  })
  const anzahlBedarf = geordnet.filter((k) => hatHandlungsbedarf(k, regelnJe.get(k.strategie))).length
  return (
    <section className="kettenkarten">
      <h3>Ketten nach Handlungsbedarf</h3>
      <p className="sicht">
        {anzahlBedarf} von {geordnet.length} Ketten mit Handlungsbedarf oder nahe an einer Grenze; diese stehen oben.
        Alle Karten sind zunächst geöffnet und lassen sich einklappen. Grün = in Ordnung, gelb = nahe an der Schwelle, rot = Schwelle überschritten oder Short im Geld.
      </p>
      {geordnet.map((k) => <KettenkarteAufklappbar key={k.kette_id} k={k} regeln={regelnJe.get(k.strategie)} />)}
    </section>
  )
}
