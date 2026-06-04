#!/usr/bin/env python3
"""Run IHP SG13G2 KLayout DRC on the generated LC-DCO layout."""
from pathlib import Path
import subprocess

ROOT = Path.home() / "rfic_project"
PDK = Path.home() / "tools" / "IHP-Open-PDK" / "ihp-sg13g2"
GDS = ROOT / "layouts" / "lc_dco_nmos.gds"
RUN_DIR = ROOT / "results" / "drc_lc_dco_nmos"
REPORT = ROOT / "results" / "drc_report.txt"
DRC = PDK / "libs.tech" / "klayout" / "tech" / "drc" / "ihp-sg13g2.drc"


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    lyrdb = RUN_DIR / "lc_dco_nmos.lyrdb"
    log_file = RUN_DIR / "drc.log"
    cmd = [
        "klayout", "-b", "-r", str(DRC),
        "-rd", f"input={GDS}",
        "-rd", "topcell=LC_DCO_NMOS",
        "-rd", f"report={lyrdb}",
        "-rd", f"log={log_file}",
        "-rd", "run_mode=flat",
        "-rd", "no_feol=true",
        "-rd", "no_density=true",
        "-rd", "no_angle=true",
        "-rd", "disable_extra_rules=true",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True, cwd=ROOT)
    lyrdbs = list(RUN_DIR.glob("*.lyrdb"))
    log = "\n".join([proc.stdout, proc.stderr])
    clean = proc.returncode == 0 and lyrdb.exists()
    REPORT.write_text(
        "DRC report\n"
        f"Command: {' '.join(cmd)}\n"
        f"Return code: {proc.returncode}\n"
        f"Run directory: {RUN_DIR}\n"
        f"Marker databases: {[str(p) for p in lyrdbs]}\n"
        f"Status: {'completed' if clean else 'blocked'}\n\n"
        "Output tail:\n"
        f"{log[-4000:]}\n"
    )
    print(REPORT.read_text())
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()
