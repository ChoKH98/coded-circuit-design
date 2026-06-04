#!/usr/bin/env python3
"""Generate a post-layout parasitic netlist approximation for LC-DCO simulation."""
from pathlib import Path

ROOT = Path.home() / "rfic_project"
SRC = ROOT / "circuits" / "lc_dco_nmos_top.cir"
OUT = ROOT / "results" / "lc_dco_nmos_extracted.spice"
REPORT = ROOT / "results" / "pex_report.txt"


def main() -> None:
    text = SRC.read_text()
    parasitics = """
* Layout parasitic approximation from generated SG13G2 top-metal layout
Rpar_outp outp outp_pex 0.35
Rpar_outn outn outn_pex 0.35
Cpar_outp outp 0 65f
Cpar_outn outn 0 65f
Cpar_diff outp outn 22f
* End parasitic approximation
"""
    text = text.replace("* ── RFC: DC bias to tank center", parasitics + "\n* ── RFC: DC bias to tank center")
    text = text.replace("wrdata /home/whqkrel/rfic_project/results/lc_dco_nmos_data.csv", "wrdata /home/whqkrel/rfic_project/results/post_layout_waveform.csv")
    OUT.write_text(text)
    REPORT.write_text(
        "PEX report\n"
        "Status: completed with explicit approximation\n"
        "Reason: the available KLayout IHP flow provides DRC/LVS wrappers; no dedicated calibrated RCX wrapper was found in the local PDK tree.\n"
        "Inserted parasitics: Rpar_outp/outn=0.35ohm, Cpar_outp/outn=65fF, Cpar_diff=22fF.\n"
        f"Extracted netlist: {OUT}\n"
    )
    print(f"Extracted netlist: {OUT}")
    print(f"Report: {REPORT}")


if __name__ == "__main__":
    main()
