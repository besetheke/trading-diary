"""Erzeugt ``oo_beispiel.csv`` — ein frei erfundener Option-Omega-Export
(AP-12a). Keine Kontodaten. Format wie der echte Export: 28 Spalten, jedes Feld
in Anführungszeichen, UTF-8 mit BOM.

Zeilen (Erwartungen siehe ``tests/test_api_backtests.py``):
  R1 IC  2026-03-02 09:32  Expired              P/L  224  1 Kontrakt
  R2 IC  2026-03-03 09:32  Stop Loss            P/L −500  1 Kontrakt
  R3 IC  2026-03-04 09:32  Expired              P/L  200  1 Kontrakt
  R4 IC  2026-03-05 09:32  Backtest Completed   P/L  −10  (offen)
  R5 SPY 2026-03-02 11:51  Exited at Spec. Time P/L   50  1 Kontrakt
  R6 DC  2025-12-30 15:05  Jahreswechsel im Verfall (Dez → Jan)
  R7 PBF 2026-03-03 11:15  Expired              P/L  800  2 Kontrakte
"""

import csv
import pathlib

KOPF = ["Date Opened", "Time Opened", "Opening Price", "Legs", "Premium", "Closing Price",
        "Date Closed", "Time Closed", "Days in Trade", "Avg. Closing Cost", "Reason For Close",
        "P/L", "P/L %", "No. of Contracts", "Funds at Close", "Margin Req.", "Underlying",
        "Strategy", "Opening Commissions + Fees", "Closing Commissions + Fees",
        "Opening Short/Long Ratio", "Closing Short/Long Ratio", "Opening VIX", "Closing VIX",
        "Gap", "Movement", "Max Profit", "Max Loss"]

IC = "-26 -IC Test- 9:32"


def zeile(d, t, kurs, legs, praemie, d2, t2, grund, pl, n, und, strat):
    return [d, t, kurs, legs, praemie, kurs, d2, t2, "0", "0", grund, pl, "1", n, "100000",
            "2770", und, strat, "6", "0", "3.1", "1", "16.1", "16.0", "1.2", "3.4", "100", "-50"]


ZEILEN = [
    zeile("2026-03-02", "09:32:00", "6850",
          "1 Mar 2 6800 P STO 2.00 | 1 Mar 2 6900 C STO 1.50 | 1 Mar 2 6770 P BTO 0.80 | "
          "1 Mar 2 6930 C BTO 0.40", "230", "2026-03-02", "16:00:00", "Expired", "224", "1",
          "SPX", IC),
    zeile("2026-03-03", "09:32:00", "6860",
          "1 Mar 3 6810 P STO 2.10 | 1 Mar 3 6910 C STO 1.40 | 1 Mar 3 6780 P BTO 0.80 | "
          "1 Mar 3 6940 C BTO 0.30", "240", "2026-03-03", "11:00:00", "Stop Loss", "-500", "1",
          "SPX", IC),
    zeile("2026-03-04", "09:32:00", "6870",
          "1 Mar 4 6820 P STO 2.00 | 1 Mar 4 6920 C STO 1.40 | 1 Mar 4 6790 P BTO 0.80 | "
          "1 Mar 4 6950 C BTO 0.40", "220", "2026-03-04", "16:00:00", "Expired", "200", "1",
          "SPX", IC),
    zeile("2026-03-05", "09:32:00", "6880",
          "1 Mar 5 6830 P STO 2.00 | 1 Mar 5 6930 C STO 1.40 | 1 Mar 5 6800 P BTO 0.80 | "
          "1 Mar 5 6960 C BTO 0.40", "220", "2026-03-05", "15:59:00", "Backtest Completed",
          "-10", "1", "SPX", IC),
    zeile("2026-03-02", "11:51:00", "686.00",
          "1 Mar 2 685 P STO 1.00 | 1 Mar 2 687 C STO 0.40 | 1 Mar 2 678 P BTO 0.10 | "
          "1 Mar 2 695 C BTO 0.02", "128", "2026-03-02", "15:57:00", "Exited at Specified Time",
          "50", "1", "SPY", "-26 SPY -IF- 11:51"),
    zeile("2025-12-30", "15:05:00", "6050",
          "1 Dec 31 6000 P STO 10.00 | 1 Dec 31 6100 C STO 3.00 | 1 Jan 2 6000 P BTO 15.00 | "
          "1 Jan 2 6100 C BTO 6.00", "-800", "2025-12-31", "15:00:00", "Exited at Specified Time",
          "50", "1", "SPX", "-26 -DC Jahr-"),
    zeile("2026-03-03", "11:15:00", "6860",
          "4 Mar 3 6855 P STO 9.00 | 2 Mar 3 6825 P BTO 4.00 | 2 Mar 3 6885 P BTO 20.00", "-600",
          "2026-03-03", "16:00:00", "Expired", "800", "2", "SPX", "0DTE -PBF-"),
]

if __name__ == "__main__":
    ziel = pathlib.Path(__file__).with_name("oo_beispiel.csv")
    with open(ziel, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(KOPF)
        w.writerows(ZEILEN)
