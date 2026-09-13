"""Geldtest AP-03: Barausgleich provisorisch anwenden, Restfaelle neu bewerten.

Eigenstaendig (ersetzt die verlorene Skriptkette). Alles im Speicher, keine Datenbank,
keine Kopie. Ausgabe nur Zaehlwerte, Aufzaehlungswerte und Pseudonyme (CLAUDE.md, Regel 2).

Provisorisch und nur in diesem Prozess: echtes Zeitformat, dateTime statt tradeTime,
notes als Code-Liste (Ep/Ex/A = Ereignis, sonst trade), Quellschluessel der Sektionen
uebersprungen, Kapitalmassnahmen als Lot-Uebertrag je conid (OF-23).
"""
import collections
import glob
import json
import pathlib
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import ingest.flex as flex  # noqa: E402
from engine.matching import bilde_legs  # noqa: E402

CENT = Decimal("0.01")
TOL = Decimal("0.02")

# ------------------------------------------------------------ provisorische Import-Anpassungen
_pflicht, _datum = flex._pflichtwert, flex._datumwert


def pflicht(attribute, name, kontext):
    if name == "tradeTime" and not attribute.get("tradeTime", "").strip() and attribute.get("dateTime", "").strip():
        name = "dateTime"
    return _pflicht(attribute, name, kontext)


def zeit(roh, kontext):
    for fmt in ("%Y%m%d;%H%M%S", "%Y%m%d", "%Y%m%d %H:%M:%S"):
        try:
            return datetime.strptime(roh, fmt)
        except ValueError:
            pass
    raise ValueError(f"{kontext}: Zeitpunkt unlesbar")


def datum(roh, kontext):
    if re.fullmatch(r"\d{8};\d{6}", roh or ""):
        return datetime.strptime(roh[:8], "%Y%m%d").date()
    return _datum(roh, kontext)


EREIGNIS = {"Ep": "expiry", "Ex": "exercise", "A": "assignment"}


def ereignistyp(attribute, kontext):
    roh = (attribute.get("notes") or "").strip()
    for c in (c.strip() for c in roh.split(";")):
        if c in EREIGNIS:
            return EREIGNIS[c], roh
    return "trade", roh or None


flex._pflichtwert, flex._zeitpunktwert, flex._datumwert = pflicht, zeit, datum
flex._ereignistyp_aus_notes = ereignistyp
flex._quell_schluessel_vergeben = lambda zeilen, sektion, datei: None


def D(w):
    return Decimal((w or "0").strip() or "0")


def tag8(w):
    w = (w or "").strip()
    return datetime.strptime(w[:8], "%Y%m%d").date() if len(w) >= 8 else None


def hat_ergebnis(p):
    rest = b""
    with open(p, "rb") as f:
        while True:
            s = f.read(1 << 22)
            if not s:
                return False
            if b"FIFOPerformanceSummaryUnderlying" in rest + s:
                return True
            rest = s[-64:]


# ------------------------------------------------------------ Einlesen
GOLDEN = REPO / "fixtures" / "golden"
dateien = [p for p in sorted(glob.glob(str(GOLDEN / "*.xml"))) if "test_lots" not in p and hat_ergebnis(p)]
execs, instrumente, ka = {}, {}, {}
ib_exec, tx_zu_tid = {}, {}
lots_je_close = collections.defaultdict(list)
for pfad in dateien:
    inhalt = flex._parse_datei(pathlib.Path(pfad))
    for z in inhalt.executions:
        execs.setdefault(z["exec_id"], z)
    for conid, satz in inhalt.instruments.items():
        if conid not in instrumente or satz.get("multiplikator") is not None:
            instrumente[conid] = satz
    for r in inhalt.corporate_actions:
        roh = json.loads(r["roh_json"])
        if roh.get("levelOfDetail") != "DETAIL":
            continue
        ka[(roh.get("actionID"), roh.get("conid"), roh.get("quantity"), r["datum"])] = {
            "conid": int(roh.get("conid") or 0), "aktion": roh.get("actionID") or roh.get("transactionID"),
            "menge": D(roh.get("quantity")), "zeit": r["datum"], "klasse": roh.get("assetCategory"),
            "mult": D(roh["multiplier"]) if roh.get("multiplier") else None,
            "kosten": D(roh["costBasis"]) if roh.get("costBasis") else None}
    del inhalt
    letzte = None
    for _, el in ET.iterparse(pfad, events=("end",)):
        a = el.attrib
        if el.tag == "Trade" and a.get("levelOfDetail") == "EXECUTION":
            ib_exec[a.get("tradeID")] = (D(a.get("fifoPnlRealized")), D(a.get("fxRateToBase") or "1"))
            tx_zu_tid[a.get("transactionID")] = a.get("tradeID")
            letzte = (a.get("tradeID"), a.get("conid"))
            el.clear()
        elif el.tag == "Lot":
            if letzte and a.get("conid") == letzte[1]:
                lots_je_close[letzte[0]].append({"offen_tx": a.get("transactionID"), "offen": tag8(a.get("openDateTime")),
                                                 "menge": abs(D(a.get("quantity")))})
            el.clear()
        elif el.tag in ("SecurityInfo", "CashTransaction", "OpenPosition", "FIFOPerformanceSummaryUnderlying", "CorporateAction"):
            el.clear()
print(f"Dateien {len(dateien)}, Ausfuehrungen {len(execs)}, Kapitalmassnahmen-Zeilen {len(ka)}")

aktionen = collections.defaultdict(list)
for k in ka.values():
    aktionen[k["aktion"]].append(k)


def zeilen_mit_uebertrag():
    rows = [dict(z) for z in execs.values()
            if instrumente.get(z["conid"], {}).get("asset_class") != "CASH" and instrumente.get(z["conid"], {}).get("multiplikator") is not None]
    inst = dict(instrumente)
    ersatz = {}
    for _aktion, ka_rows in sorted(aktionen.items(), key=lambda kv: min(r["zeit"] for r in kv[1])):
        zeitpunkt = min(r["zeit"] for r in ka_rows)
        for klasse in sorted({r["klasse"] for r in ka_rows}):
            netto, meta = collections.defaultdict(Decimal), {}
            for r in ka_rows:
                if r["klasse"] == klasse:
                    netto[r["conid"]] += r["menge"]
                    meta.setdefault(r["conid"], r)
            ab = [c for c, m in netto.items() if m < 0]
            zu = [c for c, m in netto.items() if m > 0]
            if len(ab) == 1 and len(zu) == 1:
                f = abs(netto[zu[0]]) / abs(netto[ab[0]])
                m_alt = inst.get(ab[0], {}).get("multiplikator") or meta[ab[0]]["mult"] or Decimal(1)
                m_neu = inst.get(zu[0], {}).get("multiplikator") or meta[zu[0]]["mult"] or m_alt
                if inst.get(zu[0], {}).get("multiplikator") is None:
                    inst[zu[0]] = {"asset_class": klasse, "multiplikator": m_neu, "expiry": None}
                for z in rows:
                    if z["conid"] == ab[0] and z["handelszeit"] < zeitpunkt:
                        z["conid"], z["menge"], z["preis"] = zu[0], z["menge"] * f, z["preis"] * m_alt / (f * m_neu)
                ersatz[ab[0]] = zu[0]
    return rows, inst, ersatz


rows, inst, ersatz = zeilen_mit_uebertrag()


def ende(c):
    gesehen = set()
    while c in ersatz and c not in gesehen:
        gesehen.add(c)
        c = ersatz[c]
    return c


def klasse_von(conid):
    return (inst.get(conid) or instrumente.get(conid) or {}).get("asset_class")


def basis_conid(z):
    if klasse_von(z["conid"]) == "STK":
        return ende(z["conid"])
    u = json.loads(z["roh_json"]).get("underlyingConid")
    return ende(int(u)) if u else f"ohne:{z['conid']}"


# Anschaffungskosten offener Aktien bei IB (letzter Stichtag)
letzte_datei = max(p for p in dateien if "_20260101_" in p)
ib_kosten = collections.defaultdict(Decimal)
for _, el in ET.iterparse(letzte_datei, events=("end",)):
    if el.tag == "OpenPosition" and el.attrib.get("assetCategory") == "STK":
        ib_kosten[ende(int(el.attrib["conid"]))] += D(el.attrib.get("costBasisMoney"))
    if el.tag in ("OpenPosition", "Trade", "Lot", "SecurityInfo", "CashTransaction", "FIFOPerformanceSummaryUnderlying"):
        el.clear()

lieferung = set()
for z in rows:
    if klasse_von(z["conid"]) == "STK" and z["ereignistyp"] in ("assignment", "exercise"):
        lieferung.add((z["handelszeit"], basis_conid(z)))


def auswerten(zeilen):
    erg = bilde_legs(zeilen, inst, [])
    nach_id = {z["exec_id"]: z for z in zeilen}
    unser = collections.defaultdict(Decimal)
    for leg in erg.legs:
        if not leg.offen_ja_nein:
            unser[leg.close_exec_id] += leg.brutto_pnl + leg.kommission_gesamt
    d_opt, d_stk, zut, stufen = collections.defaultdict(Decimal), collections.defaultdict(Decimal), set(), collections.Counter()
    for tid, (fifo, _fx) in ib_exec.items():
        z = nach_id.get(tid)
        if z is None or klasse_von(z["conid"]) not in ("OPT", "STK"):
            continue
        bw = basis_conid(z)
        d = unser.get(tid, Decimal(0)) - fifo
        (d_opt if klasse_von(z["conid"]) == "OPT" else d_stk)[bw] += d
        if z["ereignistyp"] in ("assignment", "exercise"):
            zut.add(bw)
        if fifo != 0 or tid in unser:
            stufen[(klasse_von(z["conid"]), "exakt" if abs(d) <= CENT else ("<=1" if abs(d) <= 1 else ">1"))] += 1
    kosten = collections.defaultdict(Decimal)
    for leg in erg.legs:
        if leg.offen_ja_nein and klasse_von(leg.conid) == "STK":
            o = nach_id[leg.open_exec_id]
            kosten[ende(leg.conid)] += (1 if o["side"] == "BUY" else -1) * leg.menge * inst[leg.conid]["multiplikator"] * o["preis"] - leg.kommission_gesamt
    return {"erg": erg, "nach_id": nach_id, "unser": unser, "d_opt": d_opt, "d_stk": d_stk, "zut": zut, "stufen": stufen, "kosten": kosten}


def einordnen(e, bw):
    d = e["d_opt"].get(bw, Decimal(0)) + e["d_stk"].get(bw, Decimal(0))
    rest = d - (e["kosten"].get(bw, Decimal(0)) - ib_kosten.get(bw, Decimal(0)))
    if abs(d) <= CENT:
        return "exakt"
    if abs(d) <= 1:
        return "KNAPP (<=1)"
    return "Praemie in offener Aktienbasis" if abs(rest) <= 1 else "OFFEN"


# ------------------------------------------------------------ Lauf A ohne Barausgleich (fuer die Pseudonyme)
A = auswerten(rows)
faelle = sorted([(einordnen(A, bw), bw) for bw in sorted(A["zut"], key=str) if einordnen(A, bw) in ("OFFEN", "KNAPP (<=1)")],
                key=lambda f: f[0])
print(f"Lauf ohne Barausgleich: {len(faelle)} Faelle (erwartet 36 = 17 knapp + 19 offen)")

# ------------------------------------------------------------ Lauf B mit Barausgleich
rows_b, angepasst = [], 0
for z in rows:
    z2 = dict(z)
    if klasse_von(z["conid"]) == "OPT" and z["ereignistyp"] in ("assignment", "exercise") and (z["handelszeit"], basis_conid(z)) not in lieferung:
        cp = D(json.loads(z["roh_json"]).get("closePrice"))
        if z2["preis"] != cp:
            z2["preis"], angepasst = cp, angepasst + 1
    rows_b.append(z2)
B = auswerten(rows_b)
print(f"\nBarausgleich (Schluss zum closePrice) angewandt auf {angepasst} Zeilen")
print("Je schliessender Ausfuehrung, ohne:", dict(sorted(A["stufen"].items())))
print("Je schliessender Ausfuehrung, mit: ", dict(sorted(B["stufen"].items())))

kat = collections.Counter()
for bw in set(B["d_opt"]) | set(B["d_stk"]):
    kat[("mit Zuteilung/Ausuebung" if bw in B["zut"] else "ohne Zuteilung", einordnen(B, bw))] += 1
print("\nBasiswerte je Kategorie mit Barausgleich:")
for k, v in sorted(kat.items()):
    print(f"  {v:>4} x {k[0]:24s} | {k[1]}")

print("\nAlte Pseudonyme, Stand mit Barausgleich:")
noch_offen = set()
for n, (art, bw) in enumerate(faelle, 1):
    neu = einordnen(B, bw)
    if neu == "OFFEN":
        noch_offen.add(bw)
    print(f"  B{n:02d} vorher {art:12s} -> jetzt {neu}")

print("\nWorauf verweisen IB-Lots bei Aktien-Schliessungen der noch offenen Faelle?")
verweis = collections.Counter()
for tid, lots in lots_je_close.items():
    z = B["nach_id"].get(tid)
    if z is None or klasse_von(z["conid"]) != "STK" or basis_conid(z) not in noch_offen:
        continue
    for lot in lots:
        o = B["nach_id"].get(tx_zu_tid.get(lot["offen_tx"]))
        verweis["transactionID nicht unter den Ausfuehrungen" if o is None else f"{klasse_von(o['conid'])} {o['ereignistyp']}"] += 1
print("  ", dict(verweis))
