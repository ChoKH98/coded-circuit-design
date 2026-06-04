"""Fix DRC metal slit violations (Slt.c.M1, Slt.c.M2) and Pin.h in KLayout batch mode.

SG13G2 slit rule (7.3): Metal polygons wider than W_slt_threshold require
metal_slit shapes (rectangular slots) spaced at max S_slt pitch.
  M1: threshold=10um, slit_width=1um, max_pitch=18um
  M2: threshold=10um, slit_width=1um, max_pitch=18um

Run via: klayout -b -r fix_drc_slits.py
"""
import klayout.db as db

GDS_IN  = "/home/whqkrel/rfic_project/layouts/lc_dco_nmos.gds"
GDS_OUT = "/home/whqkrel/rfic_project/layouts/lc_dco_nmos_drc_fixed.gds"

# SG13G2 metal slit rules
SLIT_RULES = {
    # Slt.a: min slit width = 2.8µm → use 3.0µm
    # Slt.c: max width without slit = 30µm → pitch 20µm (< 30µm - 3µm gap)
    "Metal1": {
        "draw_layer": (8, 0),   # metal1_drw
        "slit_layer": (8, 3),   # metal1_slit
        "threshold_um": 30.0,
        "slit_w_um": 3.0,
        "max_pitch_um": 20.0,
    },
    "Metal2": {
        "draw_layer": (10, 0),  # metal2_drw
        "slit_layer": (10, 3),  # metal2_slit
        "threshold_um": 30.0,
        "slit_w_um": 3.0,
        "max_pitch_um": 20.0,
    },
}

# Pin.h: topmetal2_pin height must be >= 0.8um (Pin.h rule)
PIN_LAYER    = (136, 2)   # topmetal2_pin
PIN_MIN_H_UM = 0.8

layout = db.Layout()
layout.read(GDS_IN)

# Find top cell
top = layout.top_cell()
print(f"Top cell: {top.name}, dbu={layout.dbu}")
dbu = layout.dbu

fixes_total = 0

for metal_name, rule in SLIT_RULES.items():
    dl, dp = rule["draw_layer"]
    sl, sp = rule["slit_layer"]
    thr = rule["threshold_um"]
    sw  = rule["slit_w_um"]
    pitch = rule["max_pitch_um"]

    # Get or create layers
    draw_idx = layout.layer(dl, dp)
    slit_idx = layout.layer(sl, sp)

    for shape in top.shapes(draw_idx).each():
        if not (shape.is_polygon() or shape.is_box()):
            continue
        bbox = shape.bbox()
        w_um = bbox.width() * dbu
        h_um = bbox.height() * dbu

        # Check if wide in either dimension
        wide_dim = None
        if w_um > thr:
            wide_dim = "x"
        if h_um > thr:
            wide_dim = "y"
        if not wide_dim:
            continue

        # Add slits perpendicular to wide dimension
        # Slits are rectangular cuts spaced at <= max_pitch
        slit_w_dbu = int(sw / dbu)
        pitch_dbu  = int(pitch / dbu)

        if wide_dim == "x":
            # Slits run vertically (perpendicular to x-direction)
            x = bbox.left + pitch_dbu
            while x + slit_w_dbu < bbox.right:
                slit_box = db.Box(x, bbox.bottom + slit_w_dbu,
                                  x + slit_w_dbu, bbox.top - slit_w_dbu)
                top.shapes(slit_idx).insert(slit_box)
                x += pitch_dbu
                fixes_total += 1
        else:
            # Slits run horizontally
            y = bbox.bottom + pitch_dbu
            while y + slit_w_dbu < bbox.top:
                slit_box = db.Box(bbox.left + slit_w_dbu, y,
                                  bbox.right - slit_w_dbu, y + slit_w_dbu)
                top.shapes(slit_idx).insert(slit_box)
                y += pitch_dbu
                fixes_total += 1

    print(f"  {metal_name}: added slit shapes")

# Fix Pin.h: ensure topmetal2_pin shapes have height >= PIN_MIN_H_UM
pin_layer_idx = layout.layer(*PIN_LAYER)
pin_fixes = 0
for shape in top.shapes(pin_layer_idx).each():
    if not shape.is_box():
        continue
    b = shape.bbox()
    if b.height() * dbu < PIN_MIN_H_UM:
        new_h = int(PIN_MIN_H_UM / dbu)
        fixed = db.Box(b.left, b.bottom, b.right, b.bottom + new_h)
        shape.box = fixed
        pin_fixes += 1

print(f"  Pin.h: fixed {pin_fixes} pin shapes")
fixes_total += pin_fixes

# Save fixed GDS
layout.write(GDS_OUT)
print(f"\nFixed GDS saved to {GDS_OUT}")
print(f"Total fixes applied: {fixes_total}")
