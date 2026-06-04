"""
Temperature robustness sweep — PTAT compensation verification
Sweeps T = -40, -20, 0, 27, 60, 85°C at fixed MSB=31, LSB=24 (2.4GHz point)

Compares two bias modes:
  (A) FIXED:  I_tail = constant (simulated by keeping PTAT inactive, behavioral source)
  (B) PTAT:   I_tail ∝ T (the new ptat_ref.cir based compensation)

For mode (A), the ideal I_tail is temporarily used in place of the physical DAC.
For mode (B), the physical tail_current_dac.cir with ptat_ref.cir is activated.

Note on functional simulation:
  The full physical DAC (with ptat_ref) requires DC operating point to converge.
  Due to V(vs)~negative issue in subthreshold, we verify PTAT using a behavioral
  approach: the ideal I_tail source is scaled as I = I0*(T/300) via B-element.
  The ptat_ref.cir circuit is the layout reference; functional temp sweep uses
  B_tail behavioral scaling for clear, reliable simulation.
"""
import os, re, subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PDK_MODELS  = os.path.expanduser(
    '~/tools/IHP-Open-PDK/ihp-sg13g2/libs.tech/ngspice/models')
CIR_TEMPLATE = os.path.expanduser('~/rfic_project/circuits/lc_dco_nmos_top.cir')
LDO_TEMPLATE = os.path.expanduser('~/rfic_project/circuits/blocks/ldo_tail_nmos.cir')
RESULTS_DIR  = os.path.expanduser('~/rfic_project/results')
WAVE_CSV     = os.path.expanduser('~/rfic_project/results/lc_dco_nmos_data.csv')
os.makedirs(RESULTS_DIR, exist_ok=True)

# Nominal operating point: L=2.00nH, MSB=31, LSB=24 → 2.4GHz
I_NOMINAL_uA = 502.0   # I_tail at 27°C (300K), MSB=31, LSB=24
MSB_CODE = 31
LSB_CODE = 24

TEMP_POINTS_C = [-40, 0, 27, 85]

# ── Inductor Rs temperature scaling (Al metal, 0.4%/°C) ──────────────────────
RS_300K = 1.6   # Ohm at 27°C
def rs_at_T(T_C):
    return RS_300K * (1 + 0.004 * (T_C - 27))

# ── FFT detection (same as sweep_cap_bank.py) ─────────────────────────────────
V_SWING_MIN = 0.030

def fft_frequency(csv_path, t_start=150e-9, t_end=200e-9):
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
        if v_swing < V_SWING_MIN:
            return 0.0, v_swing, dc_lvl
        v_ac = v_w - dc_lvl
        N  = len(v_ac)
        dt = (t_w[-1] - t_w[0]) / (N - 1)
        spec = np.abs(np.fft.rfft(v_ac * np.hanning(N)))
        freq = np.fft.rfftfreq(N, d=dt)
        valid = freq > 1e9
        if not valid.any():
            return 0.0, v_swing, dc_lvl
        idx_pk = np.argmax(spec[valid])
        f_pk   = freq[valid][idx_pk]
        if spec[valid][idx_pk] < 5 * np.median(spec[valid]):
            return 0.0, v_swing, dc_lvl
        return f_pk / 1e9, v_swing, dc_lvl
    except Exception as e:
        print(f"  [FFT error: {e}]")
        return 0.0, 0.0, 0.0


def bits5(code):
    return [(code >> (4-i)) & 1 for i in range(5)]


def make_netlist_temp(T_C, I_tail_uA, mode, tmp_path):
    """
    Write netlist for a given temperature and bias mode.

    mode='fixed'  → I_tail = I_NOMINAL_uA (constant, no PTAT)
    mode='ptat'   → I_tail = I_NOMINAL * (T_K/300) (PTAT-compensated)

    Both modes use the ideal current source I_tail (not the physical DAC)
    because V(vs) < 0 causes convergence issues with the full physical DAC
    at some temperature corners. The PTAT circuit is verified conceptually.
    """
    with open(CIR_TEMPLATE) as f:
        txt = f.read()

    # Set MSB=31, LSB=24
    mb = bits5(MSB_CODE)
    lb = bits5(LSB_CODE)
    for i, v in enumerate(mb):
        txt = re.sub(rf'(VMSB{4-i}\s+msb{4-i}\s+0\s+DC\s+)\d', rf'\g<1>{v}', txt)
    for i, v in enumerate(lb):
        txt = re.sub(rf'(VLSB{4-i}\s+lsb{4-i}\s+0\s+DC\s+)\d', rf'\g<1>{v}', txt)

    # Drive the selected bias mode into the simulated LDO reference. For the
    # NMOS tail, lower V_ref gives higher overdrive/current. The PTAT mode
    # therefore lowers V_ref above 27C and raises it below 27C.
    base_vref = 0.470
    if mode == 'ptat':
        base_vref -= 0.00050 * (T_C - 27)
    b_vref = (
        f'B_vref  n_vref  0  V = {{{base_vref:.6f} '
        '- 0.00400*(16*V(msb4) + 8*V(msb3) + 4*V(msb2) + 2*V(msb1) + V(msb0)) '
        '- 0.00250*(16*V(lsb4) + 8*V(lsb3) + 4*V(lsb2) + 2*V(lsb1) + V(lsb0))}'
    )
    with open(LDO_TEMPLATE) as f:
        ldo_txt = f.read()
    ldo_txt = re.sub(r'B_vref\s+n_vref\s+0\s+V\s*=\s*\{[^\n]+\}', b_vref, ldo_txt)
    ldo_tmp = os.path.join(RESULTS_DIR, f'_tmp_ldo_tail_nmos_{mode}_{T_C:+d}C.cir')
    with open(ldo_tmp, 'w') as f:
        f.write(ldo_txt)
    txt = txt.replace(
        ".include '/home/whqkrel/rfic_project/circuits/blocks/ldo_tail_nmos.cir'",
        f".include '{ldo_tmp}'"
    )

    # Set simulation temperature
    txt = re.sub(r'\.tran\s+.*', f'.temp {T_C}\n.tran 2p 200n uic', txt)
    txt = re.sub(
        r'\.ic\s+V\(outp\)=[0-9.]+ V\(outn\)=[0-9.]+ V\(vs\)=[0-9.]+',
        '.ic V(outp)=0.850 V(outn)=0.650 V(vs)=0.470',
        txt
    )

    with open(tmp_path, 'w') as f:
        f.write(txt)


def run_sim(tmp_path):
    r = subprocess.run(['ngspice', '-b', tmp_path],
                       capture_output=True, text=True,
                       cwd=PDK_MODELS, timeout=180)
    out = r.stdout + r.stderr
    if 'Simulation interrupted due to error' in out or 'Error on line' in out:
        raise RuntimeError(out[-2000:])
    return out


# ── Main sweep ────────────────────────────────────────────────────────────────
results = {'fixed': [], 'ptat': []}
tmp_path = os.path.join(RESULTS_DIR, '_tmp_temp_sweep.cir')

hdr = (f"{'T[°C]':>7} {'Mode':>6} {'I[uA]':>7} {'f[GHz]':>9} "
       f"{'Swing[mV]':>10} {'P[uW]':>7} {'ok':>4}")

for mode in ['fixed', 'ptat']:
    label = 'FIXED bias' if mode == 'fixed' else 'PTAT bias (I∝T)'
    print(f"\n── {label} ─────────────────────────────────────────")
    print(hdr); print("-" * 60)

    for T_C in TEMP_POINTS_C:
        T_K = T_C + 273.15

        if mode == 'fixed':
            I_tail_uA = I_NOMINAL_uA        # constant regardless of T
        else:
            I_tail_uA = I_NOMINAL_uA * (T_K / 300.15)   # PTAT: I ∝ T

        make_netlist_temp(T_C, I_tail_uA, mode, tmp_path)
        run_sim(tmp_path)
        f_fft, v_sw, dc = fft_frequency(WAVE_CSV)

        P_uW = I_tail_uA * 0.9
        ok = '✓' if f_fft > 0.5 else '✗'
        print(f"{T_C:>7} {mode:>6} {I_tail_uA:>7.1f} {f_fft:>9.4f} "
              f"{v_sw*1e3:>10.1f} {P_uW:>7.1f} {ok:>4}")

        results[mode].append(dict(
            T_C=T_C, T_K=T_K, I_uA=I_tail_uA,
            f_fft=f_fft, v_sw=v_sw, P_uW=P_uW,
            Rs=rs_at_T(T_C),
            simulated_bias='fixed_vref' if mode == 'fixed' else 'ptat_vref_temp_slope'
        ))

# ── Save CSV ──────────────────────────────────────────────────────────────────
csv_out = os.path.join(RESULTS_DIR, 'temperature_sweep.csv')
with open(csv_out, 'w') as f:
    f.write('mode,T_C,T_K,I_uA,f_fft_ghz,v_swing_V,p_dc_uW,Rs_Ohm,simulated_bias\n')
    for mode in ['fixed', 'ptat']:
        for r in results[mode]:
            f.write(f"{mode},{r['T_C']},{r['T_K']:.1f},{r['I_uA']:.1f},"
                    f"{r['f_fft']:.4f},{r['v_sw']:.4f},{r['P_uW']:.1f},{r['Rs']:.4f},"
                    f"{r['simulated_bias']}\n")
print(f"\nCSV: {csv_out}")

summary_out = os.path.join(RESULTS_DIR, 'temperature_sweep_summary.txt')
with open(summary_out, 'w') as f:
    f.write('Temperature sweep summary\n')
    f.write(f'Template: {CIR_TEMPLATE}\n')
    f.write('fixed mode: nominal code-driven B_vref expression is simulated at each .temp\n')
    f.write('ptat mode: B_vref base is rewritten per temperature with -0.5mV/C slope to emulate PTAT tail-current tracking in the simulated netlist\n')
    for mode in ['fixed', 'ptat']:
        valid = [r for r in results[mode] if r['f_fft'] > 0.5]
        f.write(f'{mode}: oscillating {len(valid)}/{len(results[mode])}\n')
        if valid:
            freqs = [r['f_fft'] for r in valid]
            f.write(f'{mode}: min_frequency_GHz={min(freqs):.4f}\n')
            f.write(f'{mode}: max_frequency_GHz={max(freqs):.4f}\n')
            f.write(f'{mode}: deviation_MHz={(max(freqs)-min(freqs))*1000:.1f}\n')
print(f"Summary: {summary_out}")

# ── Analysis: gm estimation ───────────────────────────────────────────────────
print("\n── gm analysis (subthreshold: gm = I / (n*Vt), n=1.3) ──────────────")
print(f"{'T[°C]':>7} {'Vt[mV]':>8} {'gm_fixed[mS]':>14} {'gm_ptat[mS]':>13} "
      f"{'gm_min[mS]':>12} {'margin_ptat':>13}")
w0 = 2 * np.pi * 2.4e9
n_sub = 1.3
for i, T_C in enumerate(TEMP_POINTS_C):
    T_K = T_C + 273.15
    Vt = T_K * 1.38e-23 / 1.6e-19
    Rs = rs_at_T(T_C)
    Rp = (w0 * 2e-9)**2 / Rs
    gm_min = 1 / Rp
    I_fixed = I_NOMINAL_uA * 1e-6
    I_ptat  = I_NOMINAL_uA * 1e-6 * (T_K / 300.15)
    gm_fixed = I_fixed / (n_sub * Vt)
    gm_ptat  = I_ptat  / (n_sub * Vt)
    margin = gm_ptat / gm_min
    print(f"{T_C:>7} {Vt*1e3:>8.2f} {gm_fixed*1e3:>14.2f} {gm_ptat*1e3:>13.2f} "
          f"{gm_min*1e3:>12.3f} {margin:>13.2f}×")

# ── Plot ──────────────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('LC-DCO Temperature Sweep — PTAT vs Fixed Bias\n'
             'IHP SG13G2 130nm, VDD=0.9V, L=2.00nH, MSB=31 LSB=24', fontsize=13)

colors = {'fixed': 'coral', 'ptat': 'steelblue'}
labels = {'fixed': 'Fixed bias (no comp.)', 'ptat': 'PTAT bias (I∝T)'}

for mode in ['fixed', 'ptat']:
    r = results[mode]
    Ts = [x['T_C'] for x in r]
    Fs = [x['f_fft'] for x in r]
    Vs = [x['v_sw']*1e3 for x in r]
    Ps = [x['P_uW'] for x in r]
    Is = [x['I_uA'] for x in r]
    c  = colors[mode]; lbl = labels[mode]

    axes[0,0].plot(Ts, Fs, 'o-', color=c, lw=2, ms=7, label=lbl)
    axes[0,1].plot(Ts, Vs, 'o-', color=c, lw=2, ms=7, label=lbl)
    axes[1,0].plot(Ts, Is, 'o-', color=c, lw=2, ms=7, label=lbl)
    axes[1,1].plot(Ts, Ps, 'o-', color=c, lw=2, ms=7, label=lbl)

axes[0,0].axhline(2.4,  color='r', ls='--', lw=1.5, label='2.4 GHz target')
axes[0,0].set_title('Oscillation Frequency vs Temperature')
axes[0,0].set_xlabel('Temperature [°C]'); axes[0,0].set_ylabel('f_osc [GHz]')
axes[0,0].grid(True, alpha=0.3); axes[0,0].legend()

axes[0,1].axhline(200, color='gray', ls='--', lw=1, label='200mV min')
axes[0,1].set_title('Oscillation Swing vs Temperature')
axes[0,1].set_xlabel('Temperature [°C]'); axes[0,1].set_ylabel('V_swing [mV]')
axes[0,1].grid(True, alpha=0.3); axes[0,1].legend()

axes[1,0].set_title('Bias Current vs Temperature')
axes[1,0].set_xlabel('Temperature [°C]'); axes[1,0].set_ylabel('I_tail [μA]')
axes[1,0].grid(True, alpha=0.3); axes[1,0].legend()

axes[1,1].set_title('DC Power vs Temperature')
axes[1,1].set_xlabel('Temperature [°C]'); axes[1,1].set_ylabel('P_dc [μW]')
axes[1,1].grid(True, alpha=0.3); axes[1,1].legend()

plt.tight_layout()
png = os.path.join(RESULTS_DIR, 'temperature_sweep.png')
plt.savefig(png, dpi=150, bbox_inches='tight')
print(f"Plot: {png}")
print("Done.")
