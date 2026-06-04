#!/usr/bin/env python3
"""Compute LC-DCO phase-noise metrics from the inductor sweep.

The Leeson/FoM metrics are computed from results/inductor_size_sweep.csv.
Two optional jitter checks run ngspice on temporary netlists under /tmp only;
the source circuit files are never modified.
"""
import csv
import math
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_DIR = Path("/home/whqkrel/rfic_project")
PDK_MODELS = Path("/home/whqkrel/tools/IHP-Open-PDK/ihp-sg13g2/libs.tech/ngspice/models")
TOP_NETLIST = PROJECT_DIR / "circuits/lc_dco_top.cir"
TANK_NETLIST = PROJECT_DIR / "circuits/blocks/lc_tank.cir"
INPUT_CSV = PROJECT_DIR / "results/inductor_size_sweep.csv"
OUT_CSV = PROJECT_DIR / "results/performance_metrics.csv"
OUT_PNG = PROJECT_DIR / "results/phase_noise_comparison.png"

K_BOLTZ = 1.38e-23
TEMP_K = 300.0
NOISE_FACTOR = 2.0
OFFSET_HZ = 1.0e6


def as_float(row, name):
    return float(row[name])


def safe_log10(value):
    if value <= 0 or not math.isfinite(value):
        return math.nan
    return math.log10(value)


def read_rows(path):
    with path.open(newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def compute_leeson_metrics(rows):
    metrics = []
    for row in rows:
        try:
            l_nh = as_float(row, "L_nH")
            q_l = as_float(row, "Q_L")
            f_fft_ghz = as_float(row, "f_fft_ghz")
            v_swing = as_float(row, "v_swing_V")
            p_dc_uw = as_float(row, "p_dc_uW")
            rs_ohm = as_float(row, "Rs_Ohm")

            f0 = f_fft_ghz * 1e9
            w0 = 2.0 * math.pi * f0
            rp = q_l * w0 * l_nh * 1e-9
            p_sig = (v_swing * v_swing) / (8.0 * rp) if rp > 0 else math.nan

            leeson_arg = (
                2.0
                * NOISE_FACTOR
                * K_BOLTZ
                * TEMP_K
                / p_sig
                * (f0 / (2.0 * q_l * OFFSET_HZ)) ** 2
                if p_sig > 0 and q_l > 0 and f0 > 0
                else math.nan
            )
            pn_leeson = 10.0 * safe_log10(leeson_arg)

            p_dc_mw = p_dc_uw / 1e3
            fom = (
                -pn_leeson
                + 20.0 * safe_log10(f0 / OFFSET_HZ)
                - 10.0 * safe_log10(p_dc_mw)
                if math.isfinite(pn_leeson)
                else math.nan
            )

            metrics.append(
                {
                    "L_nH": l_nh,
                    "Rs_Ohm": rs_ohm,
                    "Q_L": q_l,
                    "f_fft_ghz": f_fft_ghz,
                    "v_swing_V": v_swing,
                    "p_dc_uW": p_dc_uw,
                    "Rp_Ohm": rp,
                    "P_sig_uW": p_sig * 1e6 if math.isfinite(p_sig) else math.nan,
                    "PN_leeson_dBcHz": pn_leeson,
                    "FoM": fom,
                    "jitter_ps": math.nan,
                }
            )
        except Exception as exc:
            print(f"[ERROR] Leeson metric failed for row {row}: {exc}")
    return metrics


def patch_tank_text(tank_text, l_nh):
    patched = re.sub(
        r"(?m)^(L1\s+outp\s+mid_L\s+)[0-9.]+n\b",
        rf"\g<1>{l_nh:.3f}n",
        tank_text,
    )
    if patched == tank_text:
        print(f"[ERROR] Could not patch L1 value in temporary tank for L={l_nh:.2f} nH")
    return patched


def patch_top_text(top_text, temp_tank_path, wave_path):
    txt = top_text
    txt = re.sub(
        r"(?m)^(\s*\.include\s+)['\"][^'\"]*lc_tank\.cir['\"]\s*$",
        rf"\1'{temp_tank_path}'",
        txt,
    )
    txt = re.sub(
        r"(?m)^\.tran\s+\S+\s+\S+.*$",
        ".tran 2p 500n uic",
        txt,
        count=1,
    )
    txt = re.sub(
        r"wrdata\s+\S+\s+v\(outp\)\s+v\(outn\)\s+v\(vs\)",
        f"wrdata {wave_path} v(outp) v(outn) v(vs)",
        txt,
        count=1,
    )
    return txt


def find_ngspice():
    candidates = ["/usr/local/bin/ngspice", "ngspice"]
    for candidate in candidates:
        path = shutil.which(candidate) if candidate == "ngspice" else candidate
        if path and Path(path).exists():
            return path
    return "ngspice"


def load_waveform(path):
    data = np.loadtxt(path)
    if data.ndim == 1:
        data = data.reshape(1, -1)
    if data.shape[1] < 2:
        raise ValueError(f"waveform has {data.shape[1]} columns")
    return data[:, 0], data[:, 1]


def zero_crossings_positive(t, v, start_s, end_s):
    mask = (t >= start_s) & (t <= end_s)
    tw = t[mask]
    vw = v[mask]
    if len(tw) < 3:
        return np.array([])

    centered = vw - np.mean(vw)
    crossings = []
    for i in range(1, len(centered)):
        v0 = centered[i - 1]
        v1 = centered[i]
        if v0 < 0.0 <= v1 and v1 != v0:
            frac = -v0 / (v1 - v0)
            crossings.append(tw[i - 1] + frac * (tw[i] - tw[i - 1]))
    return np.array(crossings)


def jitter_for_l(l_nh):
    try:
        top_text = TOP_NETLIST.read_text()
        tank_text = TANK_NETLIST.read_text()
    except Exception as exc:
        print(f"[ERROR] Could not read source netlists for L={l_nh:.2f} nH: {exc}")
        return math.nan, math.nan

    with tempfile.TemporaryDirectory(prefix=f"lc_dco_l_{l_nh:.2f}_", dir="/tmp") as tmpdir:
        tmp = Path(tmpdir)
        temp_tank = tmp / "lc_tank_patched.cir"
        temp_top = tmp / "lc_dco_top_patched.cir"
        wave_path = tmp / "lc_dco_jitter_data.csv"
        log_path = tmp / "ngspice.log"

        try:
            temp_tank.write_text(patch_tank_text(tank_text, l_nh))
            temp_top.write_text(patch_top_text(top_text, temp_tank, wave_path))

            ngspice = find_ngspice()
            run = subprocess.run(
                [ngspice, "-b", str(temp_top)],
                cwd=str(PDK_MODELS),
                capture_output=True,
                text=True,
                timeout=240,
            )
            log_path.write_text(run.stdout + run.stderr)
            if run.returncode != 0:
                print(f"[ERROR] ngspice failed for L={l_nh:.2f} nH; see {log_path}")
                print((run.stderr or run.stdout).strip().splitlines()[-1:])
                return math.nan, math.nan
            if not wave_path.exists():
                print(f"[ERROR] ngspice produced no waveform for L={l_nh:.2f} nH")
                return math.nan, math.nan

            t, v = load_waveform(wave_path)
            zc = zero_crossings_positive(t, v, 300e-9, 500e-9)
            if len(zc) < 4:
                print(f"[ERROR] Too few zero crossings for L={l_nh:.2f} nH: {len(zc)}")
                return math.nan, math.nan

            periods = np.diff(zc)
            sigma_t = float(np.std(periods, ddof=1))
            mean_period = float(np.mean(periods))
            f0 = 1.0 / mean_period if mean_period > 0 else math.nan
            jitter_arg = (sigma_t * f0) ** 2 / (2.0 * OFFSET_HZ**2)
            l_jitter = 10.0 * safe_log10(jitter_arg)
            return sigma_t * 1e12, l_jitter
        except subprocess.TimeoutExpired:
            print(f"[ERROR] ngspice timed out for L={l_nh:.2f} nH")
        except Exception as exc:
            print(f"[ERROR] Jitter extraction failed for L={l_nh:.2f} nH: {exc}")
    return math.nan, math.nan


def apply_jitter(metrics):
    targets = {1.28, 2.00}
    for target in sorted(targets):
        print(f"\nRunning jitter transient for L={target:.2f} nH...")
        jitter_ps, pn_jitter = jitter_for_l(target)
        if math.isfinite(jitter_ps):
            print(f"  jitter_ps={jitter_ps:.4f}, PN_jitter={pn_jitter:.2f} dBc/Hz")
        else:
            print("  jitter_ps=NaN")
        for row in metrics:
            if abs(row["L_nH"] - target) < 0.005:
                row["jitter_ps"] = jitter_ps


def write_metrics(metrics):
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "L_nH",
        "Rs_Ohm",
        "Q_L",
        "f_fft_ghz",
        "v_swing_V",
        "p_dc_uW",
        "Rp_Ohm",
        "P_sig_uW",
        "PN_leeson_dBcHz",
        "FoM",
        "jitter_ps",
    ]
    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in metrics:
            writer.writerow({name: row[name] for name in fields})


def plot_metrics(metrics):
    try:
        l_vals = np.array([r["L_nH"] for r in metrics], dtype=float)
        pn_vals = np.array([r["PN_leeson_dBcHz"] for r in metrics], dtype=float)
        fom_vals = np.array([r["FoM"] for r in metrics], dtype=float)
        rp_vals = np.array([r["Rp_Ohm"] for r in metrics], dtype=float)
        p_vals = np.array([r["p_dc_uW"] for r in metrics], dtype=float)

        fig, axes = plt.subplots(2, 2, figsize=(12, 8))
        fig.suptitle("LC-DCO Phase Noise Comparison", fontsize=14)

        axes[0, 0].plot(l_vals, pn_vals, "o-", color="#1f77b4", lw=2)
        axes[0, 0].set_xlabel("L [nH]")
        axes[0, 0].set_ylabel("Leeson PN @ 1 MHz [dBc/Hz]")
        axes[0, 0].grid(True, alpha=0.3)

        axes[0, 1].plot(l_vals, fom_vals, "o-", color="#2ca02c", lw=2)
        axes[0, 1].set_xlabel("L [nH]")
        axes[0, 1].set_ylabel("FoM [dB]")
        axes[0, 1].grid(True, alpha=0.3)

        axes[1, 0].plot(l_vals, rp_vals, "o-", color="#d62728", lw=2)
        axes[1, 0].set_xlabel("L [nH]")
        axes[1, 0].set_ylabel("Rp [Ohm]")
        axes[1, 0].grid(True, alpha=0.3)

        scatter = axes[1, 1].scatter(p_vals, pn_vals, c=l_vals, cmap="viridis", s=70)
        axes[1, 1].set_xlabel("Pdc [uW]")
        axes[1, 1].set_ylabel("Leeson PN @ 1 MHz [dBc/Hz]")
        axes[1, 1].grid(True, alpha=0.3)
        cbar = fig.colorbar(scatter, ax=axes[1, 1])
        cbar.set_label("L [nH]")

        fig.tight_layout()
        fig.savefig(OUT_PNG, dpi=180)
        plt.close(fig)
    except Exception as exc:
        print(f"[ERROR] Plot generation failed: {exc}")


def fmt(value, width=12, precision=3):
    if value is None or not math.isfinite(float(value)):
        return f"{'NaN':>{width}}"
    return f"{float(value):>{width}.{precision}f}"


def print_table(metrics):
    print("\nLC-DCO phase-noise comparison")
    header = (
        f"{'L[nH]':>7} {'Q_L':>8} {'f[GHz]':>8} {'Rp[ohm]':>11} "
        f"{'P_sig[uW]':>11} {'PN[dBc/Hz]':>12} {'FoM[dB]':>10} {'jitter[ps]':>11}"
    )
    print(header)
    print("-" * len(header))
    for row in metrics:
        print(
            f"{row['L_nH']:7.2f} "
            f"{row['Q_L']:8.3f} "
            f"{row['f_fft_ghz']:8.4f} "
            f"{row['Rp_Ohm']:11.1f} "
            f"{row['P_sig_uW']:11.4f} "
            f"{row['PN_leeson_dBcHz']:12.2f} "
            f"{row['FoM']:10.2f} "
            f"{fmt(row['jitter_ps'], 11, 4)}"
        )


def main():
    try:
        rows = read_rows(INPUT_CSV)
    except Exception as exc:
        print(f"[ERROR] Could not read {INPUT_CSV}: {exc}")
        rows = []

    metrics = compute_leeson_metrics(rows)
    if not metrics:
        print("[ERROR] No metrics computed; writing empty output files where possible.")

    apply_jitter(metrics)

    try:
        write_metrics(metrics)
        print(f"\nWrote {OUT_CSV}")
    except Exception as exc:
        print(f"[ERROR] Could not write {OUT_CSV}: {exc}")

    plot_metrics(metrics)
    if OUT_PNG.exists():
        print(f"Wrote {OUT_PNG}")

    print_table(metrics)


if __name__ == "__main__":
    main()
