"""
Compare two LC-DCO inductor retunes with the same two-phase cap-bank sweep.

This script writes a self-contained netlist for each sweep point, runs ngspice,
extracts the late-window oscillation frequency using the same FFT logic as
scripts/sweep_cap_bank.py, and saves a side-by-side comparison CSV.
"""
import csv
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np


PROJECT_DIR = Path.home() / "rfic_project"
PDK_MODELS = Path.home() / "tools/IHP-Open-PDK/ihp-sg13g2/libs.tech/ngspice/models"
CIR_TEMPLATE = PROJECT_DIR / "circuits/lc_dco_top.cir"
BLOCKS_DIR = PROJECT_DIR / "circuits/blocks"
RESULTS_DIR = PROJECT_DIR / "results"
NETLIST_DIR = RESULTS_DIR / "inductor_sweep_netlists"
WAVE_CSV = RESULTS_DIR / "lc_dco_data.csv"
OUT_CSV = RESULTS_DIR / "inductor_comparison.csv"
VDD = 0.9

RESULTS_DIR.mkdir(exist_ok=True)
NETLIST_DIR.mkdir(exist_ok=True)


@dataclass(frozen=True)
class Design:
    name: str
    L_H: float
    Rs_Ohm: float
    C_F: float
    C_UNIT_MSB: float
    C_UNIT_LSB: float
    I_BASE: float
    I_UNIT_MSB: float
    I_UNIT_LSB: float


DESIGNS = [
    Design("OLD", 1.28e-9, 1.2, 1.72e-12, 97e-15, 69e-15, 150e-6, 15e-6, 7e-6),
    Design("NEW", 2.00e-9, 1.6, 1.10e-12, 62e-15, 44e-15, 96e-6, 9.6e-6, 4.5e-6),
]

PHASES = [
    ("A", [(msb, 0) for msb in [0, 8, 16, 24, 31]]),
    ("B", [(31, lsb) for lsb in [0, 8, 16, 24, 31]]),
]


def bits5(code):
    return [(code >> (4 - i)) & 1 for i in range(5)]


def estimate_f(design, msb_code, lsb_code=0):
    """Estimate tank resonant frequency for given MSB/LSB code."""
    mb = bits5(msb_code)
    lb = bits5(lsb_code)
    c_msb = sum(mb[i] * (2 ** (4 - i)) * design.C_UNIT_MSB for i in range(5))
    c_lsb = sum(lb[i] * (2 ** (4 - i)) * design.C_UNIT_LSB for i in range(5))
    C_each = design.C_F + c_msb + c_lsb
    return 1.0 / (2 * np.pi * np.sqrt(design.L_H / 2 * C_each))


def estimate_ibias_dac(design, msb_code, lsb_code=0):
    mb = bits5(int(msb_code))
    lb = bits5(int(lsb_code))
    weights = [1, 2, 4, 8, 16]
    msb_added = sum(mb[4 - i] * weights[i] * design.I_UNIT_MSB for i in range(5))
    lsb_added = sum(lb[4 - i] * weights[i] * design.I_UNIT_LSB for i in range(5))
    return design.I_BASE + msb_added + lsb_added


def estimate_ic(msb_code):
    """
    Initial conditions: outp/outn at mid-rail, vs low to keep PMOS ON at startup.
    """
    v_outp = 0.500
    v_outn = 0.300
    v_vs = 0.050
    return v_outp, v_outn, v_vs


V_SWING_MIN = 0.030   # below this = damped ringing, not sustained oscillation

def fft_frequency(csv_path, t_start=150e-9, t_end=200e-9):
    """
    FFT on the LATE window (150-200ns) only.
    Rationale:
      - Damped ringing from .ic decays within ~10-30ns
      - If oscillation is sustained, it's still present at 150ns
      - If swing < V_SWING_MIN at 150-200ns → not oscillating (return 0)
    """
    try:
        data = np.loadtxt(csv_path)
        if data.ndim == 1 or data.shape[0] < 100:
            return 0.0, 0.0, 0.0
        t = data[:, 0]; vout = data[:, 1]
        mask = (t >= t_start) & (t <= t_end)
        if mask.sum() < 50:
            return 0.0, 0.0, 0.0
        t_w = t[mask]; v_w = vout[mask]
        v_swing = v_w.max() - v_w.min()
        dc_lvl  = v_w.mean()

        # Key check: if swing is tiny, it's not oscillating
        if v_swing < V_SWING_MIN:
            return 0.0, v_swing, dc_lvl

        v_ac = v_w - dc_lvl
        N    = len(v_ac)
        dt   = (t_w[-1] - t_w[0]) / (N - 1)
        spec = np.abs(np.fft.rfft(v_ac * np.hanning(N)))
        freq = np.fft.rfftfreq(N, d=dt)
        valid = freq > 1e9
        if not valid.any():
            return 0.0, v_swing, dc_lvl
        idx_pk = np.argmax(spec[valid])
        f_pk   = freq[valid][idx_pk]
        # SNR check: peak must stand out from noise floor
        if spec[valid][idx_pk] < 5 * np.median(spec[valid]):
            return 0.0, v_swing, dc_lvl
        return f_pk / 1e9, v_swing, dc_lvl
    except Exception as e:
        print(f"  [FFT error: {e}]")
        return 0.0, 0.0, 0.0


def scale_suffix(value):
    if value >= 1e-9:
        return f"{value / 1e-9:.6g}n"
    if value >= 1e-12:
        return f"{value / 1e-12:.6g}p"
    if value >= 1e-15:
        return f"{value / 1e-15:.6g}f"
    return f"{value:.6e}"


def patch_bits(txt, msb_code, lsb_code):
    mb = bits5(msb_code)
    lb = bits5(lsb_code)
    for i, v in enumerate(mb):
        txt = re.sub(rf"(VMSB{4 - i}\s+msb{4 - i}\s+0\s+DC\s+)\d", rf"\g<1>{v}", txt)
    for i, v in enumerate(lb):
        txt = re.sub(rf"(VLSB{4 - i}\s+lsb{4 - i}\s+0\s+DC\s+)\d", rf"\g<1>{v}", txt)
    return txt


def cap_bank_subckt(name, prefix, unit_f):
    lines = [f"* Generated {name} capacitor bank", f".subckt {name} outp outn {prefix}4 {prefix}3 {prefix}2 {prefix}1 {prefix}0"]
    for bit in range(5):
        cap = scale_suffix(unit_f * (2 ** bit))
        lines.extend([
            f"C_p{bit}  outp  sp{bit}  {cap}",
            f"S_p{bit}  sp{bit}   0    {prefix}{bit}  0  SW_IDEAL",
            f"R_p{bit}  sp{bit}   0    1Meg",
            f"C_n{bit}  outn  sn{bit}  {cap}",
            f"S_n{bit}  sn{bit}   0    {prefix}{bit}  0  SW_IDEAL",
            f"R_n{bit}  sn{bit}   0    1Meg",
            "",
        ])
    lines.append(f".ends {name}")
    return "\n".join(lines)


def lc_tank_subckt(design):
    return f"""
* Generated LC tank for {design.name} design
.subckt lc_tank outp outn msb4 msb3 msb2 msb1 msb0 lsb4 lsb3 lsb2 lsb1 lsb0

L1    outp  mid_L  {scale_suffix(design.L_H)}
R_Ls  mid_L outn   {design.Rs_Ohm:.6g}

C1    outp  0  {scale_suffix(design.C_F)}
C2    outn  0  {scale_suffix(design.C_F)}

X_msb outp outn msb4 msb3 msb2 msb1 msb0 cap_bank_msb
X_lsb outp outn lsb4 lsb3 lsb2 lsb1 lsb0 cap_bank_lsb

C_ox1  outp  sub1  65f
C_ox2  outn  sub2  65f
R_sub1 sub1  0     200
C_sub1 sub1  0     40f
R_sub2 sub2  0     200
C_sub2 sub2  0     40f

.ends lc_tank
""".strip()


def standalone_blocks(design):
    return "\n\n".join([
        (BLOCKS_DIR / "cross_coupled_pair.cir").read_text(),
        cap_bank_subckt("cap_bank_msb", "msb", design.C_UNIT_MSB),
        cap_bank_subckt("cap_bank_lsb", "lsb", design.C_UNIT_LSB),
        lc_tank_subckt(design),
    ])


def make_netlist(design, phase, msb_code, lsb_code):
    txt = CIR_TEMPLATE.read_text()
    txt = re.sub(r"(?m)^\s*\.include\s+['\"][^'\"]+/circuits/blocks/[^'\"]+['\"]\s*$", "", txt)
    txt = txt.replace("* Sub-circuit blocks\n* ============================================================", 
                      "* Sub-circuit blocks\n* ============================================================\n" + standalone_blocks(design))
    txt = patch_bits(txt, msb_code, lsb_code)

    i_tail_uA = estimate_ibias_dac(design, msb_code, lsb_code) * 1e6
    txt = re.sub(r"(I_tail\s+vs\s+0\s+DC\s+)[0-9.]+u", rf"\g<1>{i_tail_uA:.3f}u", txt)

    vp, vn, vvs = estimate_ic(msb_code)
    txt = re.sub(
        r"\.ic\s+V\(outp\)=[0-9.]+ V\(outn\)=[0-9.]+ V\(vs\)=[0-9.]+",
        f".ic V(outp)={vp:.3f} V(outn)={vn:.3f} V(vs)={vvs:.3f}",
        txt,
    )
    netlist_path = NETLIST_DIR / f"lc_dco_{design.name.lower()}_phase{phase}_msb{msb_code:02d}_lsb{lsb_code:02d}.cir"
    netlist_path.write_text(txt)
    return netlist_path


def run_sim(netlist_path):
    result = subprocess.run(
        ["ngspice", "-b", str(netlist_path)],
        capture_output=True,
        text=True,
        cwd=PDK_MODELS,
        timeout=150,
    )
    return result.returncode, result.stdout + result.stderr


def run_point(design, phase, msb, lsb):
    f_est = estimate_f(design, msb, lsb) / 1e9
    ibias = estimate_ibias_dac(design, msb, lsb)
    netlist_path = make_netlist(design, phase, msb, lsb)
    code, log = run_sim(netlist_path)
    if code != 0:
        tail = "\n".join(log.splitlines()[-30:])
        raise RuntimeError(f"ngspice failed for {netlist_path}:\n{tail}")
    f_fft, v_sw, _dc = fft_frequency(WAVE_CSV)
    p_dc_uW = ibias * VDD * 1e6
    return {
        "phase": phase,
        "msb": msb,
        "lsb": lsb,
        "design": design.name,
        "L_nH": design.L_H / 1e-9,
        "ibias_uA": ibias * 1e6,
        "f_est_ghz": f_est,
        "f_fft_ghz": f_fft,
        "v_swing_V": v_sw,
        "p_dc_uW": p_dc_uW,
    }


def save_csv(rows):
    fieldnames = ["phase", "msb", "lsb", "design", "L_nH", "ibias_uA", "f_est_ghz", "f_fft_ghz", "v_swing_V", "p_dc_uW"]
    with OUT_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                "phase": row["phase"],
                "msb": row["msb"],
                "lsb": row["lsb"],
                "design": row["design"],
                "L_nH": f"{row['L_nH']:.2f}",
                "ibias_uA": f"{row['ibias_uA']:.3f}",
                "f_est_ghz": f"{row['f_est_ghz']:.6f}",
                "f_fft_ghz": f"{row['f_fft_ghz']:.6f}",
                "v_swing_V": f"{row['v_swing_V']:.6f}",
                "p_dc_uW": f"{row['p_dc_uW']:.3f}",
            })


def print_summary(rows):
    by_point = {}
    for row in rows:
        by_point.setdefault((row["phase"], row["msb"], row["lsb"]), {})[row["design"]] = row

    print("\nShared sweep-point comparison")
    print(
        "phase msb lsb | old_f old_swing old_p | new_f new_swing new_p | power_reduction"
    )
    print("-" * 91)
    for phase, points in PHASES:
        for msb, lsb in points:
            old = by_point[(phase, msb, lsb)]["OLD"]
            new = by_point[(phase, msb, lsb)]["NEW"]
            reduction = (old["p_dc_uW"] - new["p_dc_uW"]) / old["p_dc_uW"] * 100.0
            print(
                f"{phase:>5} {msb:>3} {lsb:>3} | "
                f"{old['f_fft_ghz']:>5.3f} {old['v_swing_V']:>9.3f} {old['p_dc_uW']:>6.1f} | "
                f"{new['f_fft_ghz']:>5.3f} {new['v_swing_V']:>9.3f} {new['p_dc_uW']:>6.1f} | "
                f"{reduction:>6.1f}%"
            )


def main():
    rows = []
    print("Running LC-DCO inductor comparison sweep")
    for design in DESIGNS:
        print(f"\nDesign {design.name}: L={design.L_H / 1e-9:.2f}nH Rs={design.Rs_Ohm:g}ohm")
        for phase, points in PHASES:
            for msb, lsb in points:
                row = run_point(design, phase, msb, lsb)
                rows.append(row)
                ok = "ok" if row["f_fft_ghz"] > 0.5 else "no-fft"
                print(
                    f"  phase {phase} msb={msb:02d} lsb={lsb:02d}: "
                    f"f_fft={row['f_fft_ghz']:.4f}GHz swing={row['v_swing_V']:.3f}V "
                    f"p_est={row['p_dc_uW']:.1f}uW {ok}",
                    flush=True,
                )

    save_csv(rows)
    print(f"\nCSV: {OUT_CSV}")
    print_summary(rows)


if __name__ == "__main__":
    main()
