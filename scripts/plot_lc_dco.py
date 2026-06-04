import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.signal import welch

data_path = os.path.expanduser('~/rfic_project/results/lc_dco_data.csv')

if not os.path.exists(data_path):
    print(f"ERROR: {data_path} not found. Run ngspice first.")
    exit(1)

data = np.loadtxt(data_path)
time  = data[:, 0]
voutp = data[:, 1]
if data.shape[1] >= 6:
    voutn = data[:, 3]
    vvs   = data[:, 5]
else:
    voutn = data[:, 2]
    vvs   = data[:, 3]

vdiff = voutp - voutn
dt    = time[1] - time[0]

# ── Startup detection ──────────────────────────────────────────────────────
envelope = np.abs(vdiff)
startup_idx = np.argmax(envelope > 0.5 * np.max(envelope))
t_startup = time[startup_idx] * 1e9

# ── Frequency from zero crossings (steady-state window) ───────────────────
ss_mask = time > 50e-9
t_ss    = time[ss_mask]
v_ss    = voutp[ss_mask]

v_mean = np.mean(v_ss)
crossings = np.where(np.diff(np.sign(v_ss - v_mean)) > 0)[0]
if len(crossings) >= 4:
    # Use all crossing intervals for robust frequency estimate
    periods = np.diff(t_ss[crossings])
    # Filter out outliers (startup transient artifacts)
    med = np.median(periods)
    periods = periods[np.abs(periods - med) < 0.5 * med]
    f_osc   = 1.0 / np.mean(periods) if len(periods) > 0 else 0
    f_std   = np.std(1.0 / periods) if len(periods) > 1 else 0
else:
    f_osc = 0
    f_std = 0

# ── Output swing ───────────────────────────────────────────────────────────
v_max   = np.max(voutp[ss_mask])
v_min   = np.min(voutp[ss_mask])
v_swing = v_max - v_min

print(f"{'='*50}")
print(f"  Subthreshold LC-DCO Simulation Results")
print(f"{'='*50}")
print(f"  f_osc    : {f_osc/1e9:.4f} GHz  (σ={f_std/1e6:.1f} MHz)")
print(f"  V_swing  : {v_swing:.3f} V")
print(f"  V_max    : {v_max:.3f} V")
print(f"  V_min    : {v_min:.3f} V")
print(f"  t_startup: ~{t_startup:.1f} ns")
print(f"{'='*50}")

# ── Plots ──────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle(
    f'Subthreshold LC-DCO (IHP SG13G2 130nm)\n'
    f'VDD=0.9V, W=40um, L=2.00nH low-current retune, f={f_osc/1e9:.3f}GHz',
    fontsize=13, fontweight='bold'
)

# 1. Time-domain waveform (full)
ax = axes[0, 0]
ax.plot(time * 1e9, voutp, 'b-', lw=1.5, label='V(outp)')
ax.plot(time * 1e9, voutn, 'r-', lw=1.5, label='V(outn)', alpha=0.7)
ax.set_xlabel('Time [ns]')
ax.set_ylabel('Voltage [V]')
ax.set_title('Differential Output (Full)')
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)

# 2. Steady-state zoom (last 10 cycles)
ax = axes[0, 1]
if f_osc > 0:
    t_zoom = 10 / f_osc
    zoom_mask = time > (time[-1] - t_zoom)
else:
    zoom_mask = time > 50e-9
ax.plot(time[zoom_mask] * 1e9, voutp[zoom_mask], 'b-', lw=2, label='V(outp)')
ax.plot(time[zoom_mask] * 1e9, voutn[zoom_mask], 'r-', lw=2, label='V(outn)', alpha=0.8)
ax.set_xlabel('Time [ns]')
ax.set_ylabel('Voltage [V]')
ax.set_title(f'Steady-State Zoom  (swing={v_swing:.3f}V)')
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)

# 3. Differential output + tail voltage
ax = axes[1, 0]
ax.plot(time * 1e9, vdiff, 'g-', lw=1.5, label='V(outp)−V(outn)')
ax.plot(time * 1e9, vvs,   'm-', lw=1.5, label='V(vs) tail', alpha=0.7)
ax.set_xlabel('Time [ns]')
ax.set_ylabel('Voltage [V]')
ax.set_title('Differential & Tail Node')
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)

# 4. FFT spectrum
ax = axes[1, 1]
ss_sig = vdiff[ss_mask]
N      = len(ss_sig)
dt_fft = (t_ss[-1] - t_ss[0]) / (N - 1)
freq_fft = np.fft.rfftfreq(N, d=dt_fft)
spec     = np.abs(np.fft.rfft(ss_sig)) / N
spec_db  = 20 * np.log10(spec + 1e-12)
valid_spec = (freq_fft > 0.5e9) & (freq_fft < 10e9)
if np.any(valid_spec):
    valid_idx = np.where(valid_spec)[0]
    peak_idx = valid_idx[np.argmax(spec[valid_spec])]
    guard = max(2, int(0.05e9 / (freq_fft[1] - freq_fft[0])))
    spur_mask = valid_spec.copy()
    spur_mask[max(0, peak_idx - guard):peak_idx + guard + 1] = False
    if np.any(spur_mask):
        spur_idx = np.where(spur_mask)[0][np.argmax(spec[spur_mask])]
        spur_dbc = spec_db[spur_idx] - spec_db[peak_idx]
        floor_db = np.median(spec_db[spur_mask])
        floor_dbc = floor_db - spec_db[peak_idx]
        print(f"  FFT peak : {freq_fft[peak_idx]/1e9:.4f} GHz")
        print(f"  Spur max : {spur_dbc:.1f} dBc  (transient FFT proxy)")
        print(f"  Floor med: {floor_dbc:.1f} dBc  (not PNoise)")
ax.plot(freq_fft / 1e9, spec_db, 'b-', lw=1)
if f_osc > 0:
    ax.axvline(x=f_osc / 1e9, color='r', ls='--', alpha=0.8,
               label=f'f={f_osc/1e9:.3f}GHz')
ax.set_xlim(0, min(10, freq_fft[-1] / 1e9))
ax.set_ylim(bottom=max(spec_db.min(), -80))
ax.set_xlabel('Frequency [GHz]')
ax.set_ylabel('Amplitude [dBV]')
ax.set_title('Output Spectrum (FFT)')
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)

plt.tight_layout()
save_path = os.path.expanduser('~/rfic_project/results/lc_dco_plot.png')
plt.savefig(save_path, dpi=150, bbox_inches='tight')
print(f"\nPlot saved: {save_path}")
print("Done.")
