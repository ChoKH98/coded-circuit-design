#!/usr/bin/env python3
"""Run post-layout ngspice and compare against pre-layout LC-DCO metrics."""
from pathlib import Path
import subprocess
import numpy as np
import re

ROOT = Path.home() / "rfic_project"
NETLIST = ROOT / "results" / "lc_dco_nmos_extracted.spice"
WAVE = ROOT / "results" / "post_layout_waveform.csv"
REPORT = ROOT / "results" / "post_layout_comparison.md"
PDK_MODELS = Path.home() / "tools" / "IHP-Open-PDK" / "ihp-sg13g2" / "libs.tech" / "ngspice" / "models"


def freq_ghz(path: Path) -> float:
    data = np.loadtxt(path)
    t = data[:, 0]
    v = data[:, 1]
    mask = (t >= 150e-9) & (t <= 300e-9)
    tw = t[mask]
    vw = v[mask]
    mid = 0.5 * (vw.max() + vw.min())
    x = vw - mid
    crossings = []
    for i in range(1, len(x)):
        if x[i - 1] <= 0 < x[i]:
            crossings.append(tw[i - 1] + (-x[i - 1] / (x[i] - x[i - 1])) * (tw[i] - tw[i - 1]))
    if len(crossings) < 4:
        return 0.0
    return 1.0 / np.median(np.diff(crossings)) / 1e9


def main() -> None:
    proc = subprocess.run(["ngspice", "-b", str(NETLIST)], cwd=PDK_MODELS, capture_output=True, text=True, timeout=180)
    log = proc.stdout + proc.stderr
    f_post = freq_ghz(WAVE) if WAVE.exists() else 0.0
    pre_f = 2.4027
    pre_p = 904.0
    match = re.search(r"p_dc_uw\s*=\s*([0-9.eE+-]+)", log)
    post_p = float(match.group(1)) if match else float("nan")
    REPORT.write_text(
        "# Post-Layout Simulation Comparison\n\n"
        f"Command: `ngspice -b {NETLIST}`\n\n"
        f"Return code: `{proc.returncode}`\n\n"
        "| Metric | Pre-layout | Post-layout extracted | Delta |\n"
        "| --- | ---: | ---: | ---: |\n"
        f"| Frequency | {pre_f:.4f} GHz | {f_post:.4f} GHz | {(f_post - pre_f) * 1000:.1f} MHz |\n"
        f"| Power | {pre_p:.1f} uW | {post_p:.1f} uW | {post_p - pre_p:.1f} uW |\n"
        "| Phase noise | see pre-layout phase-noise script | not recalculated by transient-only PEX run | N/A |\n\n"
        "Notes: post-layout netlist uses explicit RC parasitic approximation from `scripts/run_pex.py`.\n\n"
        "Ngspice output tail:\n\n"
        "```text\n"
        f"{log[-3000:]}\n"
        "```\n"
    )
    print(REPORT.read_text())
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
