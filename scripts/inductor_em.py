import os
os.environ.pop('PDK', None)

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from CSXCAD import ContinuousStructure
from openEMS import openEMS

sim_path = os.path.expanduser('~/rfic_project/results/inductor_em_sim')
os.makedirs(sim_path, exist_ok=True)

unit = 1e-6
f0 = 3e9
fc = 3e9

print("=" * 60)
print("  Spiral Inductor EM (Mesh-Aligned Ports)")
print("=" * 60)

FDTD = openEMS(NrTS=5000000, EndCriteria=1e-4)
CSX = ContinuousStructure()
FDTD.SetCSX(CSX)
FDTD.SetGaussExcite(f0, fc)
FDTD.SetBoundaryCond(['PML_4','PML_4','PML_4','PML_4','PML_4','PML_4'])

mesh = CSX.GetGrid()
mesh.SetDeltaUnit(unit)

metal = CSX.AddMetal('ind')
sub = CSX.AddMaterial('sub', epsilon=11.9, kappa=2.0)

n_turns = 4
w = 10
s = 5
t_met = 3
d_in = 100
d_out = d_in + 2 * n_turns * (w + s)
margin = d_out * 0.6
half = d_out / 2 + margin

z_met = 0
z_met_top = t_met
port_h = 20

sub.AddBox([-half, -half, -200], [half, half, z_met])

segments = 8
pts = []
for i in range(n_turns * segments + 1):
    a = i * 2 * np.pi / segments
    r = d_in / 2 + (i / segments) * (w + s)
    pts.append((r * np.cos(a), r * np.sin(a), r, a))

for i in range(len(pts) - 1):
    x1, y1, r1, a1 = pts[i]
    x2, y2, r2, a2 = pts[i + 1]
    ri1, ro1 = r1 - w / 2, r1 + w / 2
    ri2, ro2 = r2 - w / 2, r2 + w / 2
    p = np.array([
        [ro1*np.cos(a1), ro2*np.cos(a2), ri2*np.cos(a2), ri1*np.cos(a1)],
        [ro1*np.sin(a1), ro2*np.sin(a2), ri2*np.sin(a2), ri1*np.sin(a1)]
    ])
    metal.AddLinPoly(p, 'z', z_met, t_met)

p1x, p1y = pts[0][0], pts[0][1]
p2x, p2y = pts[-1][0], pts[-1][1]

res = w
z_lines = [-200, -150, -100, -50, 0, t_met/2, t_met,
           t_met + port_h/3, t_met + 2*port_h/3, t_met + port_h,
           t_met + 50, t_met + 100, t_met + margin]

x_lines = sorted(set(
    list(np.arange(-half, half + res, res)) +
    [p1x - w, p1x - w/2, p1x - w/4, p1x, p1x + w/4, p1x + w/2, p1x + w] +
    [p2x - w, p2x - w/2, p2x - w/4, p2x, p2x + w/4, p2x + w/2, p2x + w]
))

y_lines = sorted(set(
    list(np.arange(-half, half + res, res)) +
    [p1y - w, p1y - w/2, p1y - w/4, p1y, p1y + w/4, p1y + w/2, p1y + w] +
    [p2y - w, p2y - w/2, p2y - w/4, p2y, p2y + w/4, p2y + w/2, p2y + w]
))

mesh.SetLines('x', x_lines)
mesh.SetLines('y', y_lines)
mesh.SetLines('z', z_lines)
mesh.SmoothMeshLines('all', res, 1.4)

xm = np.array(mesh.GetLines('x'))
ym = np.array(mesh.GetLines('y'))
zm = np.array(mesh.GetLines('z'))

def snap(val, lines):
    return float(lines[np.argmin(np.abs(lines - val))])

p1x_s = snap(p1x, xm)
p1y_s = snap(p1y, ym)
p2x_s = snap(p2x, xm)
p2y_s = snap(p2y, ym)

p1x_lo = snap(p1x - w/4, xm)
p1x_hi = snap(p1x + w/4, xm)
p1y_lo = snap(p1y - w/4, ym)
p1y_hi = snap(p1y + w/4, ym)

p2x_lo = snap(p2x - w/4, xm)
p2x_hi = snap(p2x + w/4, xm)
p2y_lo = snap(p2y - w/4, ym)
p2y_hi = snap(p2y + w/4, ym)

z_port_bot = snap(z_met_top, zm)
z_port_top = snap(z_met_top + port_h, zm)

print(f"  Port1 snapped: x=[{p1x_lo},{p1x_hi}], y=[{p1y_lo},{p1y_hi}], z=[{z_port_bot},{z_port_top}]")
print(f"  Port2 snapped: x=[{p2x_lo},{p2x_hi}], y=[{p2y_lo},{p2y_hi}], z=[{z_port_bot},{z_port_top}]")

assert p1x_lo != p1x_hi, "Port1 x collapsed"
assert p1y_lo != p1y_hi, "Port1 y collapsed"
assert p2x_lo != p2x_hi, "Port2 x collapsed"
assert p2y_lo != p2y_hi, "Port2 y collapsed"
assert z_port_bot != z_port_top, "Port z collapsed"

metal.AddBox([p1x_lo, p1y_lo, z_met], [p1x_hi, p1y_hi, z_met_top])
metal.AddBox([p2x_lo, p2y_lo, z_met], [p2x_hi, p2y_hi, z_met_top])

port = [None, None]

start1 = [float(p1x_lo), float(p1y_lo), float(z_port_bot)]
stop1 = [float(p1x_hi), float(p1y_hi), float(z_port_top)]
start2 = [float(p2x_lo), float(p2y_lo), float(z_port_bot)]
stop2 = [float(p2x_hi), float(p2y_hi), float(z_port_top)]

print(f"  Port1 start={start1}, stop={stop1}")
print(f"  Port2 start={start2}, stop={stop2}")

port[0] = FDTD.AddLumpedPort(1, 50, start1, stop1, 'z', 1.0, priority=100)
port[1] = FDTD.AddLumpedPort(2, 50, start2, stop2, 'z', 0.0, priority=100)

nx = len(xm)
ny = len(ym)
nz = len(zm)
print(f"  Mesh: {nx}x{ny}x{nz} = {nx*ny*nz} cells")

CSX.Write2XML(os.path.join(sim_path, 'inductor.xml'))
print("Starting simulation...")
FDTD.Run(sim_path, cleanup=False, verbose=3)
print("Simulation completed.")

freq = np.linspace(0.1e9, 8e9, 401)
port[0].CalcPort(sim_path, freq)
port[1].CalcPort(sim_path, freq)

uf_inc = port[0].uf_inc
uf_ref = port[0].uf_ref

if np.any(np.isnan(uf_inc)) or np.max(np.abs(uf_inc)) < 1e-30:
    print("\nERROR: Port not working.")
    print(f"  max(uf_inc): {np.max(np.abs(uf_inc))}")
else:
    s11 = uf_ref / uf_inc
    z_in = 50 * (1 + s11) / (1 - s11 + 1e-30)
    omega = 2 * np.pi * freq
    L_ext = np.imag(z_in) / omega
    Q_ext = np.imag(z_in) / (np.real(z_in) + 1e-30)

    print(f"\n--- Diagnostics ---")
    print(f"  S11 @ 1GHz: {20*np.log10(abs(np.interp(1e9, freq, abs(s11)))+1e-15):.1f} dB")
    print(f"  S11 @ 3GHz: {20*np.log10(abs(np.interp(3e9, freq, abs(s11)))+1e-15):.1f} dB")

    valid = (freq > 0.3e9) & (Q_ext > 0.1) & (Q_ext < 200) & (L_ext > 0) & (L_ext < 500e-9)
    print(f"  Valid points: {np.sum(valid)}/{len(freq)}")

    if np.sum(valid) > 10:
        Q_max = np.max(Q_ext[valid])
        f_Qmax = freq[valid][np.argmax(Q_ext[valid])]
        L_2g = np.interp(2.4e9, freq[valid], L_ext[valid])
        Q_2g = np.interp(2.4e9, freq[valid], Q_ext[valid])
        print(f"\n  L @ 2.4 GHz:  {L_2g*1e9:.3f} nH")
        print(f"  Q @ 2.4 GHz:  {Q_2g:.1f}")
        print(f"  Peak Q:       {Q_max:.1f} @ {f_Qmax/1e9:.2f} GHz")

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('Spiral Inductor EM (Mesh-Aligned)', fontsize=13, fontweight='bold')

    if np.sum(valid) > 10:
        axes[0,0].plot(freq[valid]/1e9, Q_ext[valid], 'b-', lw=2)
        axes[0,0].set_title(f'Q (peak={Q_max:.1f})')
    else:
        axes[0,0].plot(freq/1e9, Q_ext, 'b-', lw=2)
        axes[0,0].set_title('Q (raw)')
    axes[0,0].set_xlabel('Freq [GHz]')
    axes[0,0].set_ylabel('Q')
    axes[0,0].grid(True, alpha=0.3)

    if np.sum(valid) > 10:
        axes[0,1].plot(freq[valid]/1e9, L_ext[valid]*1e9, 'r-', lw=2)
        axes[0,1].set_title(f'L={L_2g*1e9:.2f}nH')
    else:
        axes[0,1].plot(freq/1e9, L_ext*1e9, 'r-', lw=2)
        axes[0,1].set_title('L (raw)')
    axes[0,1].set_xlabel('Freq [GHz]')
    axes[0,1].set_ylabel('L [nH]')
    axes[0,1].grid(True, alpha=0.3)

    axes[1,0].plot(freq/1e9, 20*np.log10(np.abs(s11)+1e-15), 'b-', lw=2)
    axes[1,0].set_xlabel('Freq [GHz]')
    axes[1,0].set_ylabel('[dB]')
    axes[1,0].set_title('S11')
    axes[1,0].grid(True, alpha=0.3)

    axes[1,1].plot(freq/1e9, np.real(z_in), 'g-', lw=2, label='Re(Z)')
    axes[1,1].plot(freq/1e9, np.imag(z_in), 'm-', lw=2, label='Im(Z)')
    axes[1,1].set_xlabel('Freq [GHz]')
    axes[1,1].set_ylabel('Z [ohm]')
    axes[1,1].set_title('Z11')
    axes[1,1].grid(True, alpha=0.3)
    axes[1,1].legend()

    plt.tight_layout()
    save_path = os.path.expanduser('~/rfic_project/results/inductor_em_plot.png')
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"\nPlot saved to: {save_path}")

print("Done.")
