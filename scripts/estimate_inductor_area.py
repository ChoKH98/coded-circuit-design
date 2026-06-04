#!/usr/bin/env python3
"""Estimate square spiral inductor area for IHP SG13G2 TopMetal2."""

from __future__ import annotations

import csv
import math
from pathlib import Path


K1 = 2.34
K2 = 2.75
MU0 = 4.0 * math.pi * 1e-7

W = 9e-6
S = 2e-6
N_TURNS = 2
SHEET_RESISTANCE = 0.025

L_TARGETS_NH = [1.28, 1.52, 1.76, 2.00, 2.28, 2.56]

PROJECT_DIR = Path.home() / "rfic_project"
RESULTS_DIR = PROJECT_DIR / "results"
INP_PATH = RESULTS_DIR / "inductor.inp"
CSV_PATH = RESULTS_DIR / "inductor_area_estimate.csv"


def geometry_from_dout(d_out: float) -> tuple[float, float, float]:
    d_in = d_out - 2.0 * N_TURNS * (W + S)
    if d_in <= 0:
        raise ValueError("D_out is too small for a positive D_in")
    d_avg = (d_out + d_in) / 2.0
    rho = (d_out - d_in) / (d_out + d_in)
    return d_in, d_avg, rho


def mohan_l_h(d_out: float) -> float:
    _d_in, d_avg, rho = geometry_from_dout(d_out)
    return K1 * MU0 * (N_TURNS**2) * d_avg / (1.0 + K2 * rho)


def solve_dout(target_l_h: float) -> float:
    min_d_out = 2.0 * N_TURNS * (W + S) * 1.000001
    lo = min_d_out
    hi = 100e-6

    while mohan_l_h(hi) < target_l_h:
        hi *= 2.0
        if hi > 0.02:
            raise RuntimeError(f"failed to bracket L={target_l_h:.6e} H")

    for _ in range(120):
        mid = (lo + hi) / 2.0
        if mohan_l_h(mid) < target_l_h:
            lo = mid
        else:
            hi = mid

    return (lo + hi) / 2.0


def read_existing_geometry() -> str | None:
    if not INP_PATH.exists():
        return None

    lines = INP_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines:
        if "turns" in line.lower() and "din" in line.lower():
            return line.strip("* ")
    return f"{INP_PATH} exists ({len(lines)} lines)"


def estimate_row(l_nh: float, baseline_area: float | None) -> dict[str, float]:
    d_out = solve_dout(l_nh * 1e-9)
    d_in, d_avg, _rho = geometry_from_dout(d_out)
    area = d_out**2
    rs_est = SHEET_RESISTANCE * (N_TURNS * 4.0 * d_avg) / W
    vs_paper = 1.0 if baseline_area is None else area / baseline_area
    return {
        "L[nH]": l_nh,
        "D_out[um]": d_out * 1e6,
        "D_in[um]": d_in * 1e6,
        "Area[um^2]": area * 1e12,
        "Area[mm^2]": area * 1e6,
        "vs_paper": vs_paper,
        "Rs_est[Ohm]": rs_est,
    }


def print_table(rows: list[dict[str, float]]) -> None:
    print(
        f"{'L[nH]':>7} | {'D_out[um]':>10} | {'D_in[um]':>9} | "
        f"{'Area[um^2]':>11} | {'Area[mm^2]':>10} | {'vs_paper':>8} | {'Rs_est[Ohm]':>11}"
    )
    print("-" * 88)
    for row in rows:
        print(
            f"{row['L[nH]']:7.2f} | "
            f"{row['D_out[um]']:10.2f} | "
            f"{row['D_in[um]']:9.2f} | "
            f"{row['Area[um^2]']:11.2f} | "
            f"{row['Area[mm^2]']:10.6f} | "
            f"{row['vs_paper']:8.3f} | "
            f"{row['Rs_est[Ohm]']:11.3f}"
        )


def write_csv(rows: list[dict[str, float]]) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "L[nH]",
        "D_out[um]",
        "D_in[um]",
        "Area[um^2]",
        "Area[mm^2]",
        "vs_paper",
        "Rs_est[Ohm]",
    ]
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    existing = read_existing_geometry()
    if existing:
        print(f"Existing geometry check: {existing}")
    else:
        print(f"Existing geometry check: {INP_PATH} not found; skipped")
    print()

    rows: list[dict[str, float]] = []
    baseline_area: float | None = None
    for l_nh in L_TARGETS_NH:
        row = estimate_row(l_nh, baseline_area)
        if baseline_area is None:
            baseline_area = row["Area[um^2]"] / 1e12
            row["vs_paper"] = 1.0
        rows.append(row)

    print_table(rows)
    write_csv(rows)
    print(f"\nSaved CSV: {CSV_PATH}")


if __name__ == "__main__":
    main()
