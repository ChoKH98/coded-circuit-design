#!/usr/bin/env python3
"""Generate a conservative SG13G2 LC-DCO layout placeholder in KLayout."""
from pathlib import Path
import pya

ROOT = Path.home() / "rfic_project"
LAYOUT_DIR = ROOT / "layouts"
RESULTS_DIR = ROOT / "results"


def box_um(x1, y1, x2, y2, dbu):
    return pya.Box(int(round(x1 / dbu)), int(round(y1 / dbu)), int(round(x2 / dbu)), int(round(y2 / dbu)))


def text_um(text, x, y, dbu, size=5.0):
    t = pya.Text(text, int(round(x / dbu)), int(round(y / dbu)))
    t.size = int(round(size / dbu))
    return t


def main() -> None:
    LAYOUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    ly = pya.Layout()
    ly.dbu = 0.001
    dbu = ly.dbu
    top = ly.create_cell("LC_DCO_NMOS")

    metal1 = ly.layer(8, 0)
    metal2 = ly.layer(10, 0)
    metal5 = ly.layer(67, 0)
    topmetal1 = ly.layer(126, 0)
    topmetal2 = ly.layer(134, 0)
    pin = ly.layer(134, 2)
    text = ly.layer(134, 25)

    # Cross-coupled NMOS pair and LDO/tail source placement markers.
    top.shapes(metal1).insert(box_um(-80, -40, -15, 40, dbu))
    top.shapes(metal1).insert(box_um(15, -40, 80, 40, dbu))
    top.shapes(metal2).insert(box_um(-20, -80, 20, -45, dbu))
    top.shapes(metal2).insert(box_um(-120, -105, 120, -85, dbu))

    # Symmetric top-metal tank conductors around the oscillator core.
    top.shapes(topmetal2).insert(box_um(-160, 90, 160, 110, dbu))
    top.shapes(topmetal2).insert(box_um(-160, -110, 160, -90, dbu))
    top.shapes(topmetal1).insert(box_um(-170, -90, -150, 90, dbu))
    top.shapes(topmetal1).insert(box_um(150, -90, 170, 90, dbu))

    # Cap-bank arrays: wide separated metal plates, one row per bank side.
    x0 = -145
    for i in range(10):
        x = x0 + i * 32
        top.shapes(metal5).insert(box_um(x, 125, x + 20, 155, dbu))
        top.shapes(metal5).insert(box_um(x, -155, x + 20, -125, dbu))
        top.shapes(metal2).insert(box_um(x + 7, 112, x + 13, 125, dbu))
        top.shapes(metal2).insert(box_um(x + 7, -125, x + 13, -112, dbu))

    # Pins.
    pins = {
        "outp": (-185, 95, -165, 115),
        "outn": (165, -115, 185, -95),
        "vdd": (-120, -125, -80, -105),
        "vss": (80, -125, 120, -105),
        "vs": (-15, -100, 15, -80),
    }
    for name, b in pins.items():
        top.shapes(pin).insert(box_um(*b, dbu))
        top.shapes(text).insert(text_um(name, b[0], b[1], dbu))

    for label, x, y in [
        ("cross_coupled_pair_nmos", -78, 48),
        ("ldo_tail_nmos", -18, -72),
        ("lc_tank_topmetal", -70, 116),
        ("msb_lsb_cap_bank", -80, 162),
    ]:
        top.shapes(text).insert(text_um(label, x, y, dbu, 4.0))

    gds = LAYOUT_DIR / "lc_dco_nmos.gds"
    oas = LAYOUT_DIR / "lc_dco_nmos.oas"
    ly.write(str(gds))
    ly.write(str(oas))

    report = RESULTS_DIR / "layout_generation_report.txt"
    report.write_text(
        "LC-DCO layout generation report\n"
        "Top cell: LC_DCO_NMOS\n"
        "PDK layer source: IHP SG13G2 sg13g2.map\n"
        "Layers used: Metal1 8/0, Metal2 10/0, Metal5 67/0, TopMetal1 126/0, TopMetal2 134/0, pins 134/2\n"
        "Placed: cross-coupled NMOS marker, LC tank top-metal conductors, cap-bank arrays, LDO/tail marker\n"
        f"GDS: {gds}\nOAS: {oas}\n"
    )
    print(f"GDS: {gds}")
    print(f"OAS: {oas}")
    print(f"Report: {report}")


if __name__ == "__main__":
    main()
