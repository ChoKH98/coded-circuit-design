"""Fix Pin.h: move topmetal2_pin shapes inside topmetal2_drw metal regions."""
import klayout.db as db

GDS_IN  = "/home/whqkrel/rfic_project/layouts/lc_dco_nmos_drc_fixed.gds"
GDS_OUT = "/home/whqkrel/rfic_project/layouts/lc_dco_nmos_drc_fixed.gds"

layout = db.Layout()
layout.read(GDS_IN)
top = layout.top_cell()
dbu = layout.dbu

drw_layer = layout.layer(134, 0)   # topmetal2_drw
pin_layer = layout.layer(134, 2)   # topmetal2_pin

# Collect metal bounding boxes
metals = []
for s in top.shapes(drw_layer).each():
    metals.append(s.bbox())

def nearest_metal(pin_bbox):
    """Return the metal bbox with smallest distance to pin center."""
    pc = pin_bbox.center()
    best, best_d = None, float("inf")
    for m in metals:
        mc = m.center()
        d = abs(pc.x - mc.x) + abs(pc.y - mc.y)
        if d < best_d:
            best, best_d = m, d
    return best

fixes = 0
shapes_to_replace = []
for shape in top.shapes(pin_layer).each():
    b = shape.bbox()
    metal = nearest_metal(b)
    if metal is None:
        continue

    # Clamp pin so it fits inside metal bbox (shrink by 10 dbu margin)
    margin = int(1.0 / dbu)  # 1µm margin from each metal edge
    # Intersection of pin bbox with metal (shrunk by margin) — clip to fit strictly inside
    inner = db.Box(metal.left + margin, metal.bottom + margin,
                   metal.right - margin, metal.top - margin)
    # Move pin center inside inner, preserve pin size (clamp if pin > inner)
    pw = min(b.width(),  inner.width())
    ph = min(b.height(), inner.height())
    # Clamp center to inner region
    cx = max(inner.left  + pw // 2, min(b.center().x, inner.right  - pw // 2))
    cy = max(inner.bottom + ph // 2, min(b.center().y, inner.top   - ph // 2))
    new_box = db.Box(cx - pw // 2, cy - ph // 2, cx + pw // 2, cy + ph // 2)
    if new_box != b:
        shapes_to_replace.append((shape, new_box))
        fixes += 1
        print(f"  Pin ({b.left*dbu:.0f},{b.bottom*dbu:.0f})-({b.right*dbu:.0f},{b.top*dbu:.0f})"
              f" → ({new_box.left*dbu:.0f},{new_box.bottom*dbu:.0f})-({new_box.right*dbu:.0f},{new_box.top*dbu:.0f})")

for shape, new_box in shapes_to_replace:
    shape.box = new_box

layout.write(GDS_OUT)
print(f"\nFixed {fixes} Pin.h violations. Saved to {GDS_OUT}")
