import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import subprocess
import re

results_dir = os.path.expanduser('~/rfic_project/results')
os.makedirs(results_dir, exist_ok=True)

# ============================================================
# 1. Inductor Parameters
# ============================================================
n_turns = 4
w = 10          # trace width [um]
s = 5           # trace spacing [um]
t = 3           # metal thickness [um]
d_in = 100      # inner diameter [um]
nhinc = 3       # filaments in height
nwinc = 5       # filaments in width
rho = 2.8e-2    # resistivity [ohm*um] (aluminum)

# Frequency sweep
freqs_ghz = [0.1, 0.5, 1.0, 1.5, 2.0, 2.4, 3.0, 4.0, 5.0, 6.0, 8.0]

print("=" * 60)
print("  Spiral Inductor Analysis (FastHenry)")
print("=" * 60)
print(f"  {n_turns}T, W={w}um, S={s}um, T={t}um, Din={d_in}um")

# ============================================================
# 2. Generate octagonal spiral geometry
# ============================================================
segments_per_turn = 8

all_points = []
for i in range(n_turns * segments_per_turn + 1):
    angle = i * 2 * np.pi / segments_per_turn
    r = d_in / 2 + (i / segments_per_turn) * (w + s)
    x = r * np.cos(angle)
    y = r * np.sin(angle)
    all_points.append((x, y))

# ============================================================
# 3. Write FastHenry input file
# ============================================================
inp_path = os.path.join(results_dir, 'inductor.inp')

with open(inp_path, 'w') as f:
    f.write("* Spiral Inductor for FastHenry\n")
    f.write(f"* {n_turns} turns, W={w}um, S={s}um, Din={d_in}um\n\n")
    f.write(f".Units um\n\n")
    f.write(f".Default sigma={1/rho:.6e} nhinc={nhinc} nwinc={nwinc}\n\n")

    # Define nodes
    for i, (x, y) in enumerate(all_points):
        f.write(f"N{i} x={x:.4f} y={y:.4f} z=0\n")
    f.write("\n")

    # Define segments
    for i in range(len(all_points) - 1):
        f.write(f"E{i} N{i} N{i+1} w={w} h={t}\n")
    f.write("\n")

    # External port: first node to last node
    f.write(f".external N0 N{len(all_points)-1}\n\n")

    # Frequency sweep
    f.write(f".freq fmin=1e8 fmax=8e9 ndec=3\n\n")
    f.write(".end\n")
print(f"  Input file: {inp_path}")
print(f"  Nodes: {len(all_points)}, Segments: {len(all_points)-1}")

# ============================================================
# 4. Run FastHenry
# ============================================================
print("\nRunning FastHenry...")
result = subprocess.run(
    ['fasthenry', inp_path],
    capture_output=True, text=True, cwd=results_dir
)

print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
if result.returncode != 0:
    print("STDERR:", result.stderr[-500:])
    print("FastHenry failed!")
else:
    print("FastHenry completed successfully.")

# ============================================================
# 5. Parse results (Zc.mat file)
# ============================================================
zc_path = os.path.join(results_dir, 'Zc.mat')

freq_list = []
L_list = []
R_list = []
Q_list = []
current_freq = None

if os.path.exists(zc_path):
    print(f"\nParsing results from: {zc_path}")
    with open(zc_path, 'r') as f:
        lines = f.readlines()

    for line in lines:
        m = re.match(r'Impedance matrix for frequency = ([0-9.eE+\-]+)', line)
        if m:
            current_freq = float(m.group(1))
            continue
        m2 = re.match(r'\s+([0-9.eE+\-]+)\s+\+([0-9.eE+\-]+)j', line)
        if m2 and current_freq:
            R_val = float(m2.group(1))
            X_val = float(m2.group(2))
            omega = 2 * np.pi * current_freq
            L_val = X_val / omega
            Q_val = X_val / R_val if R_val > 0 else 0
            freq_list.append(current_freq)
            R_list.append(R_val)
            L_list.append(L_val)
            Q_list.append(Q_val)
            current_freq = None

if freq_list:
    freq_arr = np.array(freq_list)
    L_arr = np.array(L_list)
    R_arr = np.array(R_list)
    Q_arr = np.array(Q_list)

    L_2g = np.interp(2.4e9, freq_arr, L_arr)
    R_2g = np.interp(2.4e9, freq_arr, R_arr)
    Q_2g = np.interp(2.4e9, freq_arr, Q_arr)
    Q_max = np.max(Q_arr)
    f_Qmax = freq_arr[np.argmax(Q_arr)]

    print(f"\n{'='*60}")
    print(f"  FastHenry Results")
    print(f"{'='*60}")
    print(f"  L @ 2.4 GHz:  {L_2g*1e9:.3f} nH")
    print(f"  R @ 2.4 GHz:  {R_2g:.2f} ohm")
    print(f"  Q @ 2.4 GHz:  {Q_2g:.1f}")
    print(f"  Peak Q:       {Q_max:.1f} @ {f_Qmax/1e9:.2f} GHz")
    print(f"{'='*60}")

    # Print table
    print(f"\n  {'Freq[GHz]':>10} {'L[nH]':>8} {'R[ohm]':>8} {'Q':>8}")
    print(f"  {'-'*38}")
    for i in range(len(freq_arr)):
        print(f"  {freq_arr[i]/1e9:>10.1f} {L_arr[i]*1e9:>8.3f} {R_arr[i]:>8.2f} {Q_arr[i]:>8.1f}")

    # ============================================================
    # 6. Plots
    # ============================================================
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f'Spiral Inductor (FastHenry)\n{n_turns}T, W={w}um, S={s}um, Din={d_in}um',
                 fontsize=13, fontweight='bold')

    axes[0,0].plot(freq_arr/1e9, Q_arr, 'bo-', lw=2, ms=6)
    axes[0,0].axvline(x=2.4, color='green', ls=':', alpha=0.7, label='2.4 GHz')
    axes[0,0].set_xlabel('Freq [GHz]')
    axes[0,0].set_ylabel('Q')
    axes[0,0].set_title(f'Q Factor (peak={Q_max:.1f} @ {f_Qmax/1e9:.1f}GHz)')
    axes[0,0].grid(True, alpha=0.3)
    axes[0,0].legend()

    axes[0,1].plot(freq_arr/1e9, L_arr*1e9, 'ro-', lw=2, ms=6)
    axes[0,1].set_xlabel('Freq [GHz]')
    axes[0,1].set_ylabel('L [nH]')
    axes[0,1].set_title(f'Inductance (L@2.4G={L_2g*1e9:.2f}nH)')
    axes[0,1].grid(True, alpha=0.3)

    axes[1,0].plot(freq_arr/1e9, R_arr, 'go-', lw=2, ms=6)
    axes[1,0].set_xlabel('Freq [GHz]')
    axes[1,0].set_ylabel('R [ohm]')
    axes[1,0].set_title('AC Resistance (skin effect)')
    axes[1,0].grid(True, alpha=0.3)

    axes[1,1].plot(freq_arr/1e9, L_arr*1e9, 'r-', lw=2, label='L [nH]')
    ax2 = axes[1,1].twinx()
    ax2.plot(freq_arr/1e9, Q_arr, 'b--', lw=2, label='Q')
    axes[1,1].set_xlabel('Freq [GHz]')
    axes[1,1].set_ylabel('L [nH]', color='r')
    ax2.set_ylabel('Q', color='b')
    axes[1,1].set_title('L and Q vs Frequency')
    axes[1,1].grid(True, alpha=0.3)

    plt.tight_layout()
    save_path = os.path.join(results_dir, 'inductor_fasthenry_plot.png')
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"\nPlot saved to: {save_path}")
else:
    print("\nNo results parsed. Check Zc.mat file:")
    if os.path.exists(zc_path):
        with open(zc_path, 'r') as f:
            print(f.read()[:500])
    else:
        print(f"  {zc_path} not found")
        print("  Files in results dir:")
        for f in os.listdir(results_dir):
            print(f"    {f}")

print("Done.")
