#!/usr/bin/env python3
"""Fallback Magic DRC/extraction for generated SG13G2 LC-DCO layout."""
from pathlib import Path
import subprocess

ROOT = Path.home() / "rfic_project"
PDK = Path.home() / "tools" / "IHP-Open-PDK" / "ihp-sg13g2"
TECH = PDK / "libs.tech" / "magic" / "ihp-sg13g2.tech"
GDS = ROOT / "layouts" / "lc_dco_nmos.gds"
RUN_DIR = ROOT / "results" / "magic_lc_dco_nmos"
SCRIPT = RUN_DIR / "magic_drc_extract.tcl"
REPORT = ROOT / "results" / "magic_drc_extract_report.txt"


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    SCRIPT.write_text(
        f"""
gds readonly true
gds read {GDS}
load LC_DCO_NMOS
drc style drc(full)
drc check
set count [drc count total]
puts "MAGIC_DRC_TOTAL $count"
extract do local
extract all
ext2spice lvs
ext2spice cthresh 0
ext2spice rthresh 0
ext2spice -o {RUN_DIR / 'lc_dco_nmos_magic.spice'}
quit -noprompt
"""
    )
    cmd = ["magic", "-dnull", "-noconsole", "-T", str(TECH), str(SCRIPT)]
    proc = subprocess.run(cmd, cwd=RUN_DIR, capture_output=True, text=True, timeout=180)
    out = proc.stdout + proc.stderr
    blocked = (
        "Don't know how to read GDS-II" in out
        or "couldn't be read" in out
        or "Failed to load technology" in out
        or not (RUN_DIR / "lc_dco_nmos_magic.spice").exists()
    )
    REPORT.write_text(
        "Magic DRC/extraction fallback report\n"
        f"Command: {' '.join(cmd)}\n"
        f"Return code: {proc.returncode}\n"
        f"Status: {'blocked' if blocked else 'completed'}\n"
        f"Run directory: {RUN_DIR}\n"
        f"Extracted netlist: {RUN_DIR / 'lc_dco_nmos_magic.spice'}\n\n"
        "Output tail:\n"
        f"{out[-5000:]}\n"
    )
    print(REPORT.read_text())
    if proc.returncode != 0 or blocked:
        raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
