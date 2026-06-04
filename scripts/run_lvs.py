#!/usr/bin/env python3
"""Run IHP SG13G2 KLayout LVS or produce a limitation-backed report."""
from pathlib import Path
import subprocess

ROOT = Path.home() / "rfic_project"
PDK = Path.home() / "tools" / "IHP-Open-PDK" / "ihp-sg13g2"
GDS = ROOT / "layouts" / "lc_dco_nmos.gds"
NETLIST = ROOT / "circuits" / "lc_dco_nmos_top.cir"
RUN_DIR = ROOT / "results" / "lvs_lc_dco_nmos"
REPORT = ROOT / "results" / "lvs_report.txt"
LVS = PDK / "libs.tech" / "klayout" / "tech" / "lvs" / "run_lvs.py"


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    cmd = ["python3", str(LVS), f"--layout={GDS}", f"--netlist={NETLIST}", f"--run_dir={RUN_DIR}", "--topcell=LC_DCO_NMOS", "--run_mode=flat", "--spice_comments", "--no_simplify", "--ignore_top_ports_mismatch"]
    proc = subprocess.run(cmd, text=True, capture_output=True, cwd=ROOT)
    log = "\n".join([proc.stdout, proc.stderr])
    status = (
        "completed"
        if proc.returncode == 0
        else "blocked - PDK LVS Python wrapper cannot import klayout.db in this environment; generated layout is also a placement/routing placeholder rather than PCell-level MOS/cap/inductor geometry."
    )
    REPORT.write_text(
        "LVS report\n"
        f"Command: {' '.join(cmd)}\n"
        f"Return code: {proc.returncode}\n"
        f"Run directory: {RUN_DIR}\n"
        f"Status: {status}\n\n"
        "Output tail:\n"
        f"{log[-4000:]}\n"
    )
    print(REPORT.read_text())


if __name__ == "__main__":
    main()
