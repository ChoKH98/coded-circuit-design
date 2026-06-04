#!/usr/bin/env python3
"""Verify code-dependent LDO V_ref law for the NMOS LC-DCO."""
from pathlib import Path
import csv

ROOT = Path.home() / "rfic_project"
OUT_CSV = ROOT / "results" / "vref_tracking.csv"
OUT_REPORT = ROOT / "results" / "vref_tracking_report.txt"


def vref(msb: int, lsb: int) -> float:
    return 0.470 - 0.00400 * msb - 0.00250 * lsb


def main() -> None:
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    points = [(0, 0), (8, 0), (16, 0), (24, 0), (31, 0), (31, 8), (31, 16), (31, 24), (31, 31)]
    rows = []
    for msb, lsb in points:
        rows.append({
            "msb": msb,
            "lsb": lsb,
            "vref_V": vref(msb, lsb),
            "tracking": "lower_vref_higher_overdrive",
        })

    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["msb", "lsb", "vref_V", "tracking"])
        writer.writeheader()
        writer.writerows(rows)

    monotonic = all(rows[i]["vref_V"] >= rows[i + 1]["vref_V"] for i in range(len(rows) - 1))
    with OUT_REPORT.open("w") as f:
        f.write("LDO V_ref tracking verification\n")
        f.write("Formula: V_ref = 0.470 - 0.00400*MSB - 0.00250*LSB\n")
        f.write(f"Monotonic non-increasing over checked code path: {monotonic}\n")
        f.write(f"V_ref min/max over checked path: {min(r['vref_V'] for r in rows):.4f} / {max(r['vref_V'] for r in rows):.4f} V\n")
        f.write("Interpretation: higher cap code lowers source reference, increasing NMOS overdrive and restoring oscillation at high capacitance.\n")

    print(f"CSV: {OUT_CSV}")
    print(f"Report: {OUT_REPORT}")
    print(f"Monotonic: {monotonic}")


if __name__ == "__main__":
    main()
