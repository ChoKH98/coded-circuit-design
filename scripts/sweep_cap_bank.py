"""
CAP BANK frequency sweep — Phase 2
Two-phase sweep:
  Phase A: MSB sweep (LSB=0) — coarse tuning range
  Phase B: MSB=31, LSB sweep — fine tuning to reach 2.4GHz

Headroom fix:
  Larger inductor retune:
  L is increased from 1.28nH to 2.00nH. Tank capacitances and ideal
  verification tail currents are scaled by 1.28/2.00 to preserve the
  frequency map while reducing gm/current demand.

FFT-based frequency detection (robust vs fixed-threshold meas).
"""
import os, re, subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PDK_MODELS   = os.path.expanduser(
    '~/tools/IHP-Open-PDK/ihp-sg13g2/libs.tech/ngspice/models')
CIR_TEMPLATE = os.path.expanduser('~/rfic_project/circuits/lc_dco_nmos_top.cir')
RESULTS_DIR  = os.path.expanduser('~/rfic_project/results')
WAVE_CSV     = os.path.expanduser('~/rfic_project/results/lc_dco_nmos_data.csv')
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── Tank parameters ────────────────────────────────────────────────────────
L_H        = 4.00e-9
Rs_Ohm     = 2.5
C_F        = 1.975e-12
C_UNIT_MSB = 62e-15
C_UNIT_LSB = 44e-15

# Current DAC verification uses an ideal tail source because the simple NMOS
# mirror runs out of headroom at the low-vs operating point.
# Base=96uA; MSB unit=9.6uA; LSB unit=4.5uA after larger-L power retune.


def bits5(code):
    return [(code >> (4-i)) & 1 for i in range(5)]


def estimate_f(msb_code, lsb_code=0):
    """Estimate tank resonant frequency for given MSB/LSB code."""
    mb = bits5(msb_code); lb = bits5(lsb_code)
    c_msb = sum(mb[i] * (2**(4-i)) * C_UNIT_MSB for i in range(5))
    c_lsb = sum(lb[i] * (2**(4-i)) * C_UNIT_LSB for i in range(5))
    C_each = C_F + c_msb + c_lsb
    return 1.0 / (2*np.pi * np.sqrt(L_H/2 * C_each))


def estimate_ibias_dac(msb_code, lsb_code=0):
    """Expected I_tail injected as ideal current source.
    IHP sg13_lv_pmos |Vthp|~0.625V → V(vs)~20-50mV < mirror Vdsat,
    so NMOS mirror DAC is replaced with ideal source for verification.
    I_BASE=96uA, I_UNIT_MSB=9.6uA, I_UNIT_LSB=4.5uA.
    MSB=31+LSB=31: 96+297.6+139.5 = 533.1uA"""
    I_BASE = 96e-6
    I_UNIT_MSB = 9.6e-6
    I_UNIT_LSB = 4.5e-6
    mb = bits5(int(msb_code))
    lb = bits5(int(lsb_code))
    weights = [1, 2, 4, 8, 16]
    msb_added = sum(mb[4-i] * weights[i] * I_UNIT_MSB for i in range(5))
    lsb_added = sum(lb[4-i] * weights[i] * I_UNIT_LSB for i in range(5))
    return I_BASE + msb_added + lsb_added


def estimate_ic(msb_code):
    """
    Initial conditions for NMOS-only topology: tank nodes near VDD with a
    differential perturbation, source node near the code-programmed V_ref.
    """
    v_outp = 0.850
    v_outn = 0.650
    v_vs   = 0.470
    return v_outp, v_outn, v_vs


def make_netlist(msb_code, lsb_code, tmp_path, wave_path):
    """Write netlist with MSB/LSB codes, adapted .ic, and correct I_tail."""
    with open(CIR_TEMPLATE) as f:
        txt = f.read()
    mb = bits5(msb_code); lb = bits5(lsb_code)
    for i, v in enumerate(mb):
        txt = re.sub(rf'(VMSB{4-i}\s+msb{4-i}\s+0\s+DC\s+)\d', rf'\g<1>{v}', txt)
    for i, v in enumerate(lb):
        txt = re.sub(rf'(VLSB{4-i}\s+lsb{4-i}\s+0\s+DC\s+)\d', rf'\g<1>{v}', txt)
    # Physical DAC sets I_tail automatically via MSB/LSB bits — no regex needed
    # Set ideal tail current value
    i_tail_uA = estimate_ibias_dac(msb_code, lsb_code) * 1e6
    # NMOS top uses code-driven LDO tail bias rather than an ideal I_tail source.

    # Initial conditions
    vp, vn, vvs = estimate_ic(msb_code)
    txt = re.sub(
        r'\.ic\s+V\(outp\)=[0-9.]+ V\(outn\)=[0-9.]+ V\(vs\)=[0-9.]+',
        f'.ic V(outp)={vp:.3f} V(outn)={vn:.3f} V(vs)={vvs:.3f}',
        txt
    )
    txt = re.sub(
        r'wrdata\s+/home/whqkrel/rfic_project/results/lc_dco_nmos_data\.csv',
        f'wrdata {wave_path}',
        txt
    )
    with open(tmp_path, 'w') as f:
        f.write(txt)


def run_sim(tmp_path):
    r = subprocess.run(['ngspice', '-b', tmp_path],
                       capture_output=True, text=True,
                       cwd=PDK_MODELS, timeout=150)
    out = r.stdout + r.stderr
    if 'Simulation interrupted due to error' in out or 'Error on line' in out:
        raise RuntimeError(out[-2000:])
    return out


V_SWING_MIN = 0.030   # below this = damped ringing, not sustained oscillation

def fft_frequency(csv_path, t_start=150e-9, t_end=200e-9):
    """
    FFT on the LATE window (150-200ns) only.
    Rationale:
      - Damped ringing from .ic decays within ~10-30ns
      - If oscillation is sustained, it's still present at 150ns
      - If swing < V_SWING_MIN at 150-200ns → not oscillating (return 0)
    """
    try:
        data = np.loadtxt(csv_path)
        if data.ndim == 1 or data.shape[0] < 100:
            return 0.0, 0.0, 0.0
        t = data[:, 0]; vout = data[:, 1]
        mask = (t >= t_start) & (t <= t_end)
        if mask.sum() < 50:
            return 0.0, 0.0, 0.0
        t_w = t[mask]; v_w = vout[mask]
        v_swing = v_w.max() - v_w.min()
        dc_lvl  = v_w.mean()

        # Key check: if swing is tiny, it's not oscillating
        if v_swing < V_SWING_MIN:
            return 0.0, v_swing, dc_lvl

        v_ac = v_w - dc_lvl
        N    = len(v_ac)
        dt   = (t_w[-1] - t_w[0]) / (N - 1)
        spec = np.abs(np.fft.rfft(v_ac * np.hanning(N)))
        freq = np.fft.rfftfreq(N, d=dt)
        valid = freq > 1e9
        if not valid.any():
            return 0.0, v_swing, dc_lvl
        idx_pk = np.argmax(spec[valid])
        f_pk   = freq[valid][idx_pk]
        # SNR check: peak must stand out from noise floor
        if spec[valid][idx_pk] < 5 * np.median(spec[valid]):
            return 0.0, v_swing, dc_lvl
        return f_pk / 1e9, v_swing, dc_lvl
    except Exception as e:
        print(f"  [FFT error: {e}]")
        return 0.0, 0.0, 0.0


def crossing_frequency(csv_path, t_start=150e-9, t_end=300e-9):
    try:
        data = np.loadtxt(csv_path)
        if data.ndim == 1 or data.shape[0] < 100:
            return 0.0
        t = data[:, 0]
        v = data[:, 1]
        mask = (t >= t_start) & (t <= t_end)
        if mask.sum() < 100:
            return 0.0
        tw = t[mask]
        vw = v[mask]
        mid = 0.5 * (vw.max() + vw.min())
        x = vw - mid
        crossings = []
        for i in range(1, len(x)):
            if x[i - 1] <= 0.0 and x[i] > 0.0:
                dt = tw[i] - tw[i - 1]
                if dt <= 0:
                    continue
                frac = -x[i - 1] / (x[i] - x[i - 1])
                crossings.append(tw[i - 1] + frac * dt)
        if len(crossings) < 4:
            return 0.0
        periods = np.diff(crossings)
        return 1.0 / np.median(periods) / 1e9
    except Exception as e:
        print(f"  [crossing error: {e}]")
        return 0.0


def run_point(msb, lsb, tmp_path):
    f_est  = estimate_f(msb, lsb)
    ibias  = estimate_ibias_dac(msb, lsb)
    _, _, vvs = estimate_ic(msb)
    wave_path = os.path.join(RESULTS_DIR, f'lc_dco_nmos_msb{msb:02d}_lsb{lsb:02d}.csv')
    make_netlist(msb, lsb, tmp_path, wave_path)
    run_sim(tmp_path)
    if not os.path.exists(wave_path):
        raise RuntimeError(f'ngspice did not produce waveform: {wave_path}')
    f_fft, v_sw, dc = fft_frequency(wave_path)
    f_cross = crossing_frequency(wave_path)
    if f_cross > 0.5 and v_sw >= V_SWING_MIN:
        f_fft = f_cross
    ok = '✓' if f_fft > 0.5 else '✗'
    print(f"{msb:>5} {lsb:>5} {ibias*1e6:>9.0f} {vvs:>7.3f} "
          f"{f_est/1e9:>8.4f} {f_fft:>8.4f} {v_sw:>9.3f} {dc:>7.3f} {ok}")
    return (msb, lsb, ibias, f_est/1e9, f_fft, v_sw, dc)


tmp_path = os.path.join(RESULTS_DIR, '_tmp_sweep.cir')
hdr = f"{'MSB':>5} {'LSB':>5} {'Ibus[uA]':>9} {'IC_vs':>7} {'f_est':>8} {'f_FFT':>8} {'Swing[V]':>9} {'DC[V]':>7}"

# ══════════════════════════════════════════════════════════════
# Phase A: MSB coarse sweep (LSB=0)
# ══════════════════════════════════════════════════════════════
print("\n── Phase A: MSB Sweep (LSB=0) ─────────────────────────────")
print(hdr); print("-"*65)
msb_codes = list(range(32))
results_A = [run_point(m, 0, tmp_path) for m in msb_codes]


# ══════════════════════════════════════════════════════════════
# Phase B: LSB sweep with MSB=31 (fine tuning to 2.4GHz)
# ══════════════════════════════════════════════════════════════
print("\n── Phase B: LSB Sweep (MSB=31) — target 2.4GHz ────────────")
print(hdr); print("-"*65)
lsb_codes = list(range(32))
results_B = [run_point(31, l, tmp_path) for l in lsb_codes]


# ── Save CSV ───────────────────────────────────────────────────
all_results = results_A + results_B
csv_out = os.path.join(RESULTS_DIR, 'cap_bank_sweep.csv')
with open(csv_out, 'w') as f:
    f.write('phase,msb,lsb,ibias_uA,f_est_ghz,f_fft_ghz,v_swing_V,dc_V\n')
    for ph, rlist in [('A', results_A), ('B', results_B)]:
        for r in rlist:
            f.write(f"{ph},{r[0]},{r[1]},{r[2]*1e6:.0f},"
                    f"{r[3]:.4f},{r[4]:.4f},{r[5]:.4f},{r[6]:.4f}\n")
print(f"\nCSV: {csv_out}")

# ── Plot ───────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('LC-DCO CAP BANK 2-Phase Sweep\n'
             'IHP SG13G2 130nm, VDD=0.9V, L=2.00nH, low-current retune', fontsize=13)

for ax_row, (results, title_sfx, x_label, xkey) in zip(
    axes,
    [(results_A, 'Phase A: MSB Sweep (LSB=0)', 'MSB Code', 0),
     (results_B, 'Phase B: LSB Sweep (MSB=31)', 'LSB Code', 1)]):

    valid = [(r[xkey], r[4], r[5], r[2]) for r in results if r[4] > 0.5]
    if not valid:
        for ax in ax_row: ax.text(0.5, 0.5, 'No oscillation', ha='center')
        continue
    xs, freqs, swings, ibs = zip(*valid)

    ax_row[0].plot(xs, freqs, 'bo-', lw=2, ms=7)
    ax_row[0].axhline(2.4, color='r', ls='--', lw=1.5, label='2.4 GHz')
    ax_row[0].set_ylabel('f_osc [GHz]')
    ax_row[0].set_title(f'Frequency — {title_sfx}')
    ax_row[0].set_xlabel(x_label)
    ax_row[0].grid(True, alpha=0.3); ax_row[0].legend()

    ax_row[1].plot(xs, [s*1e3 for s in swings], 'go-', lw=2, ms=7)
    ax_row[1].axhline(200, color='gray', ls='--', label='200 mV min')
    ax_row[1].set_ylabel('V_swing [mV]')
    ax_row[1].set_title(f'Swing — {title_sfx}')
    ax_row[1].set_xlabel(x_label)
    ax_row[1].grid(True, alpha=0.3); ax_row[1].legend()

plt.tight_layout()
png = os.path.join(RESULTS_DIR, 'cap_bank_sweep.png')
plt.savefig(png, dpi=150, bbox_inches='tight')
print(f"Plot: {png}")

# ── Summary ────────────────────────────────────────────────────
valid_B = [(r[1], r[4], r[5], r[2]) for r in results_B if r[4] > 0.5]
valid_all = [r for r in all_results if r[4] > 0.5]
summary_out = os.path.join(RESULTS_DIR, 'cap_bank_sweep_summary.txt')
with open(summary_out, 'w') as f:
    f.write('Cap bank sweep summary\n')
    f.write(f'Template: {CIR_TEMPLATE}\n')
    f.write(f'Points: {len(all_results)}\n')
    f.write(f'Oscillating points: {len(valid_all)}\n')
    if valid_all:
        freqs_all = [r[4] for r in valid_all]
        f.write(f'Min frequency GHz: {min(freqs_all):.4f}\n')
        f.write(f'Max frequency GHz: {max(freqs_all):.4f}\n')
        f.write(f'Tuning range GHz: {(max(freqs_all)-min(freqs_all)):.4f}\n')
    else:
        f.write('Min frequency GHz: N/A\nMax frequency GHz: N/A\n')
print(f"Summary: {summary_out}")
if valid_B:
    lsbs, freqs, swings, ibs = zip(*valid_B)
    fa = np.array(freqs)
    idx = np.argmin(np.abs(fa - 2.4))
    print(f"\n✓ Closest to 2.4GHz: MSB=31 LSB={lsbs[idx]}, "
          f"f={freqs[idx]:.4f}GHz, Ibias={ibs[idx]*1e6:.0f}μA, "
          f"swing={swings[idx]*1e3:.0f}mV")
    print(f"  Min freq reached: {min(freqs):.4f}GHz "
          f"(LSB={lsbs[list(fa).index(min(freqs))]})")
else:
    print("\nWARNING: Phase B — no oscillation detected with MSB=31")

print("Done.")
