"""Regel 7: Trennen deliveryType / settlementPolicyMethod barausgeglichene von physischen Zuteilungen?

Nur Zaehl- und Aufzaehlungswerte (CLAUDE.md, Regel 2). Liest die Golden-Exporte roh, ohne Import.
"Mit Lieferung" = zur selben Zeit eine Aktienzeile mit Zuteilung/Ausuebung auf dem underlyingConid.
"""
import collections
import glob
import pathlib
import xml.etree.ElementTree as ET

GOLDEN = str(pathlib.Path(__file__).resolve().parents[2] / "fixtures" / "golden")
EREIGNIS = {"A", "Ex"}


def codes(a):
    return {c.strip() for c in (a.get("notes") or "").split(";")}


sec, opt_zeilen, stk_zeilen = {}, {}, set()
for pfad in sorted(glob.glob(GOLDEN + r"\*.xml")):
    if "test_lots" in pfad:
        continue
    for _, el in ET.iterparse(pfad, events=("end",)):
        a = el.attrib
        if el.tag == "SecurityInfo" and a.get("assetCategory") == "OPT":
            sec[a.get("conid")] = (a.get("deliveryType") or "(leer)", a.get("settlementPolicyMethod") or "(leer)")
            el.clear()
        elif el.tag == "Trade" and a.get("levelOfDetail") == "EXECUTION":
            if codes(a) & EREIGNIS:
                if a.get("assetCategory") == "OPT":
                    opt_zeilen[a.get("tradeID")] = (a.get("conid"), a.get("underlyingConid"), a.get("dateTime"),
                                                    a.get("deliveryType") or "(leer)", a.get("underlyingSymbol") and "mit" or "ohne")
                elif a.get("assetCategory") == "STK":
                    stk_zeilen.add((a.get("conid"), a.get("dateTime")))
            el.clear()
        elif el.tag in ("Lot", "CashTransaction", "OpenPosition", "FIFOPerformanceSummaryUnderlying", "CorporateAction"):
            el.clear()

tab = collections.Counter()
for _tid, (conid, ucon, zeit, dtyp_trade, _) in opt_zeilen.items():
    lieferung = "mit Lieferung" if (ucon, zeit) in stk_zeilen else "ohne Lieferung"
    dtyp_sec, spm = sec.get(conid, ("(keine SecurityInfo)", "(keine SecurityInfo)"))
    tab[(lieferung, f"Trade.deliveryType={dtyp_trade}", f"SecurityInfo.deliveryType={dtyp_sec}", f"settlementPolicyMethod={spm}")] += 1
print(f"Zuteilungen/Ausuebungen von Optionen: {len(opt_zeilen)}")
for k, v in sorted(tab.items()):
    print(f"  {v:>5} x " + " | ".join(k))
