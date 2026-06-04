import os
os.environ.pop('PDK', None)

import gdsfactory as gf
import numpy as np

gf.gpdk.PDK.activate()

c = gf.Component("nmos_basic")

LAYER_ACTIV = (1, 0)
LAYER_GATPOLY = (5, 0)
LAYER_METAL1 = (8, 0)
LAYER_CONT = (6, 0)
LAYER_NPLUS = (2, 0)

W = 1.0
L = 0.13
cont_size = 0.16
cont_enc = 0.06
poly_ext = 0.2

active_width = L + 2 * (cont_size + 2 * cont_enc + 0.1)
c.add_polygon([(- active_width/2, -W/2), (active_width/2, -W/2), (active_width/2, W/2), (-active_width/2, W/2)], layer=LAYER_ACTIV)
c.add_polygon([(-(active_width+0.1)/2, -(W+0.1)/2), ((active_width+0.1)/2, -(W+0.1)/2), ((active_width+0.1)/2, (W+0.1)/2), (-(active_width+0.1)/2, (W+0.1)/2)], layer=LAYER_NPLUS)
c.add_polygon([(-L/2, -(W/2+poly_ext)), (L/2, -(W/2+poly_ext)), (L/2, W/2+poly_ext), (-L/2, W/2+poly_ext)], layer=LAYER_GATPOLY)

src_x = -(L/2 + cont_enc + cont_size/2 + 0.05)
drn_x = (L/2 + cont_enc + cont_size/2 + 0.05)
cs = cont_size / 2

c.add_polygon([(src_x-cs, -cs), (src_x+cs, -cs), (src_x+cs, cs), (src_x-cs, cs)], layer=LAYER_CONT)
c.add_polygon([(drn_x-cs, -cs), (drn_x+cs, -cs), (drn_x+cs, cs), (drn_x-cs, cs)], layer=LAYER_CONT)

m1w = (cont_size + 0.1) / 2
m1h = W * 0.4
c.add_polygon([(src_x-m1w, -m1h), (src_x+m1w, -m1h), (src_x+m1w, m1h), (src_x-m1w, m1h)], layer=LAYER_METAL1)
c.add_polygon([(drn_x-m1w, -m1h), (drn_x+m1w, -m1h), (drn_x+m1w, m1h), (drn_x-m1w, m1h)], layer=LAYER_METAL1)

output_path = os.path.expanduser("~/rfic_project/layouts/nmos_basic.gds")
c.write_gds(output_path)
print(f"NMOS layout saved to: {output_path}")

ind = gf.Component("spiral_inductor")

n_turns = 3
width = 5.0
spacing = 3.0
inner_radius = 30.0
LAYER_TOPMETAL = (10, 0)

points = []
segments_per_turn = 32
total_segments = n_turns * segments_per_turn
for i in range(total_segments + 1):
    angle = i * (2 * np.pi / segments_per_turn)
    radius = inner_radius + (i / segments_per_turn) * (width + spacing)
    x = radius * np.cos(angle)
    y = radius * np.sin(angle)
    points.append((x, y))

path = gf.Path(points)
cross = gf.CrossSection(sections=[gf.Section(width=width, layer=LAYER_TOPMETAL)])
ind.add_ref(gf.path.extrude(path, cross_section=cross))

ind_path = os.path.expanduser("~/rfic_project/layouts/spiral_inductor.gds")
ind.write_gds(ind_path)
print(f"Spiral inductor saved to: {ind_path}")

top = gf.Component("rfic_test_chip")
nmos_ref = top.add_ref(c)
nmos_ref.dmove((0, 0))
ind_ref = top.add_ref(ind)
ind_ref.dmove((100, 0))

chip_path = os.path.expanduser("~/rfic_project/layouts/rfic_test_chip.gds")
top.write_gds(chip_path)
print(f"Test chip saved to: {chip_path}")

print(f"\n{'='*50}")
print(f"  Layout Summary")
print(f"{'='*50}")
print(f"  NMOS: {c.dsize}")
print(f"  Inductor: {n_turns} turns, R={inner_radius}um")
print(f"  Chip: {top.dsize}")
print(f"{'='*50}")
print(f"\nView in KLayout:")
print(f"  klayout {chip_path}")
