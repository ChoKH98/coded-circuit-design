"""
Inductor size sweep — Phase 3
Sweeps L from 1.28nH (paper baseline) to 2.56nH (2x paper)
Fixed operating point: MSB=31, LSB=24 (~2.4 GHz target)

Scaling rules derived from two measured data points:
  L=1.28nH (paper), L=2.00nH (tested design)

  Rs  = Rs0 * (L/L0)^0.645   [empirical fit to the two anchor points]
  C_F = K / L                 [keeps f_max constant at ~4.8GHz]
  I_BASE = 192 / L_nH [uA]   [empirical 1/L fit to the two anchor points]
"""
import os, re, math, shutil, subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PDK_MODELS   = os.path.expanduser(
    '~/tools/IHP-Open-PDK/ihp-sg13g2/libs.tech/ngspice/models')
CIR_TEMPLATE = os.path.expanduser('~/rfic_project/circuits/lc_dco_top.cir')
TANK_CIR     = os.path.expanduser('~/rfic_project/circuits/blocks/lc_tank.cir')
RESULTS_DIR  = os.path.expanduser('~/rfic_project/results')
WAVE_CSV     = os.path.expanduser('~/rfic_project/results/lc_dco_data.csv')
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── Anchor points (measured / tested) ─────────────────────────────────────
L0_nH   = 1.28   # paper baseline
Rs0_Ohm = 1.20
I0_uA   = 150.0  # I_BASE at L0
CF0_pF  = 1.72   # C_F at L0
RS_ALPHA = 0.645  # Rs ~ L^alpha  (fit to two data points)

# ── Sweep definition ──────────────────────────────────────────────────────
# From paper's L (1.28nH) to 2x paper's L (2.56nH)
L_SWEEP_nH = [1.28, 1.52, 1.76, 2.00, 2.28, 2.56]

# Fixed operating point for all L values
MSB_CODE = 31
LSB_CODE = 24

# ── Parameter scaling ─────────────────────────────────────────────────────
def scale_params(L_nH):
    """Return (Rs, C_F_pF, C_UNIT_MSB_fF, C_UNIT_LSB_fF, I_BASE_uA, I_UNIT_MSB_uA, I_UNIT_LSB_uA)"""
    ratio = L_nH / L0_nH
    Rs    = Rs0_Ohm * (ratio ** RS_ALPHA)
    C_F   = CF0_pF / ratio                        # keeps f_max constant
    C_msb = 97e-15 * (C_F / CF0_pF)               # scale cap bank units
    C_lsb = 69e-15 * (C_F / CF0_pF)
    I_base = 192.0 / L_nH                          # 1/L empirical fit [uA]
    I_msb  = I_base * (9.6 / 96.0)
    I_lsb  = I_base * (4.5 / 96.0)
    return Rs, C_F, C_msb, C_lsb, I_base, I_msb, I_lsb


def estimate_f(L_nH, C_F_pF, C_msb_fF, C_lsb_fF, msb_code, lsb_code):
    """Estimate tank resonant frequency."""
    mb = [(msb_code >> (4-i)) & 1 for i in range(5)]
    lb = [(lsb_code >> (4-i)) & 1 for i in range(5)]
    c_msb = sum(mb[i] * (2**(4-i)) * C_msb_fF * 1e-15 for i in range(5))
    c_lsb = sum(lb[i] * (2**(4-i)) * C_lsb_fF * 1e-15 for i in range(5))
    C_each = C_F_pF * 1e-12 + c_msb + c_lsb
    L_H = L_nH * 1e-9
    return 1.0 / (2*math.pi * math.sqrt(L_H/2 * C_each))


# ── Netlist generation ────────────────────────────────────────────────────
def bits5(code):
    return [(code >> (4-i)) & 1 for i in range(5)]


def make_netlist(L_nH, Rs, C_F_pF, C_msb_fF, C_lsb_fF, I_tail_uA, tmp_path):
    """Write a standalone netlist with patched lc_tank and I_tail.
    Approach: read the top-level template AND tank subcircuit, then write
    the tank inline (modified) into a single self-contained file."""

    with open(CIR_TEMPLATE) as f:
        top = f.read()
    with open(TANK_CIR) as f:
        tank_orig = f.read()

    # Patch lc_tank subcircuit: L, Rs, C1/C2
    tank = tank_orig
    tank = re.sub(r'(L1\s+outp\s+mid_L\s+)[0-9.]+n', rf'\g<1>{L_nH:.3f}n', tank)
    tank = re.sub(r'(R_Ls\s+mid_L\s+outn\s+)[0-9.]+', rf'\g<1>{Rs:.4f}', tank)
    tank = re.sub(r'(C1\s+outp\s+0\s+)[0-9.]+p', rf'\g<1>{C_F_pF:.4f}p', tank)
    tank = re.sub(r'(C2\s+outn\s+0\s+)[0-9.]+p', rf'\g<1>{C_F_pF:.4f}p', tank)

    # Patch MSB=31 and LSB=24 bits
    mb = bits5(MSB_CODE)
    lb = bits5(LSB_CODE)
    for i, v in enumerate(mb):
        top = re.sub(rf'(VMSB{4-i}\s+msb{4-i}\s+0\s+DC\s+)\d', rf'\g<1>{v}', top)
    for i, v in enumerate(lb):
        top = re.sub(rf'(VLSB{4-i}\s+lsb{4-i}\s+0\s+DC\s+)\d', rf'\g<1>{v}', top)

    # Patch I_tail
    top = re.sub(
        r'(I_tail\s+vs\s+0\s+DC\s+)[0-9.]+u',
        rf'\g<1>{I_tail_uA:.1f}u',
        top
    )

    # Remove the .include for lc_tank so we can inject the patched subcircuit inline
    top = re.sub(r"\.include\s+'[^']*lc_tank\.cir'\n", '', top)

    combined = top.rstrip() + '\n\n' + tank.strip() + '\n'
    with open(tmp_path, 'w') as f:
        f.write(combined)


# ── Simulation & FFT ──────────────────────────────────────────────────────
V_SWING_MIN = 0.030

def run_sim(tmp_path):
    r = subprocess.run(['ngspice', '-b', tmp_path],
                       capture_output=True, text=True,
                       cwd=PDK_MODELS, timeout=180)
    return r.stdout + r.stderr


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
        N    = len(v_ac)
        dt   = (t_w[-1] - t_w[0]) / (N - 1)
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


# ── Main sweep ────────────────────────────────────────────────────────────
print("\n── Inductor Size Sweep (MSB=31, LSB=24 ≈ 2.4GHz) ───────────────────")
print(f"{'L[nH]':>7} {'Rs[Ω]':>7} {'Q_L':>6} {'C_F[pF]':>8} {'I_base[uA]':>11} "
      f"{'f_est[GHz]':>11} {'f_fft[GHz]':>11} {'Swing[V]':>9} {'P[uW]':>7} {'ok':>4}")
print("-" * 90)

tmp_path = os.path.join(RESULTS_DIR, '_tmp_L_sweep.cir')
results = []

for L_nH in L_SWEEP_nH:
    Rs, C_F, C_msb, C_lsb, I_base, I_msb, I_lsb = scale_params(L_nH)

    # Total I_tail at MSB=31, LSB=24
    mb = bits5(MSB_CODE)
    lb = bits5(LSB_CODE)
    weights = [16, 8, 4, 2, 1]
    I_msb_total = sum(mb[i] * weights[i] * I_msb for i in range(5))
    I_lsb_total = sum(lb[i] * weights[i] * I_lsb for i in range(5))
    I_tail_uA = I_base + I_msb_total + I_lsb_total

    Q_L = 2 * math.pi * 2.4e9 * L_nH * 1e-9 / Rs
    f_est = estimate_f(L_nH, C_F, C_msb * 1e15, C_lsb * 1e15, MSB_CODE, LSB_CODE)

    make_netlist(L_nH, Rs, C_F, C_msb * 1e15, C_lsb * 1e15, I_tail_uA, tmp_path)
    run_sim(tmp_path)
    f_fft, v_sw, dc = fft_frequency(WAVE_CSV)

    P_uW = I_tail_uA * 0.9
    ok = '✓' if f_fft > 0.5 else '✗'
    print(f"{L_nH:>7.2f} {Rs:>7.4f} {Q_L:>6.2f} {C_F:>8.4f} {I_tail_uA:>11.1f} "
          f"{f_est/1e9:>11.4f} {f_fft:>11.4f} {v_sw:>9.4f} {P_uW:>7.1f} {ok:>4}")

    results.append(dict(
        L_nH=L_nH, Rs=Rs, Q_L=Q_L, C_F_pF=C_F,
        I_base_uA=I_base, I_tail_uA=I_tail_uA,
        f_est_ghz=f_est/1e9, f_fft_ghz=f_fft,
        v_swing_V=v_sw, p_dc_uW=P_uW
    ))

# ── Save CSV ──────────────────────────────────────────────────────────────
csv_out = os.path.join(RESULTS_DIR, 'inductor_size_sweep.csv')
with open(csv_out, 'w') as f:
    f.write('L_nH,Rs_Ohm,Q_L,C_F_pF,I_base_uA,I_tail_uA,f_est_ghz,f_fft_ghz,v_swing_V,p_dc_uW\n')
    for r in results:
        f.write(f"{r['L_nH']:.2f},{r['Rs']:.4f},{r['Q_L']:.4f},{r['C_F_pF']:.4f},"
                f"{r['I_base_uA']:.1f},{r['I_tail_uA']:.1f},"
                f"{r['f_est_ghz']:.4f},{r['f_fft_ghz']:.4f},"
                f"{r['v_swing_V']:.4f},{r['p_dc_uW']:.1f}\n")
print(f"\nCSV saved: {csv_out}")

# ── Plot ──────────────────────────────────────────────────────────────────
valid = [r for r in results if r['f_fft_ghz'] > 0.5]
if valid:
    Ls   = [r['L_nH']      for r in valid]
    Ps   = [r['p_dc_uW']   for r in valid]
    Swgs = [r['v_swing_V'] * 1e3 for r in valid]
    Qs   = [r['Q_L']       for r in valid]
    Fs   = [r['f_fft_ghz'] for r in valid]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('LC-DCO Inductor Size Sweep\n'
                 'IHP SG13G2 130nm, VDD=0.9V, MSB=31, LSB=24 (~2.4GHz)',
                 fontsize=13)

    axes[0,0].plot(Ls, Ps, 'ro-', lw=2, ms=8)
    axes[0,0].set_xlabel('L [nH]'); axes[0,0].set_ylabel('P_dc [μW]')
    axes[0,0].set_title('Power Consumption vs L')
    axes[0,0].grid(True, alpha=0.3)
    axes[0,0].axvline(1.28, color='b', ls='--', lw=1, label='paper (1.28nH)')
    axes[0,0].axvline(2.56, color='g', ls='--', lw=1, label='2× paper (2.56nH)')
    axes[0,0].legend()

    axes[0,1].plot(Ls, Swgs, 'bo-', lw=2, ms=8)
    axes[0,1].set_xlabel('L [nH]'); axes[0,1].set_ylabel('V_swing [mV]')
    axes[0,1].set_title('Oscillation Swing vs L')
    axes[0,1].axhline(200, color='gray', ls='--', lw=1, label='200mV min')
    axes[0,1].grid(True, alpha=0.3); axes[0,1].legend()

    axes[1,0].plot(Ls, Qs, 'go-', lw=2, ms=8)
    axes[1,0].set_xlabel('L [nH]'); axes[1,0].set_ylabel('Q_L at 2.4GHz')
    axes[1,0].set_title('Tank Q-factor vs L')
    axes[1,0].grid(True, alpha=0.3)

    axes[1,1].plot(Ls, Fs, 'mo-', lw=2, ms=8)
    axes[1,1].axhline(2.4, color='r', ls='--', lw=1.5, label='2.4 GHz')
    axes[1,1].set_xlabel('L [nH]'); axes[1,1].set_ylabel('f_osc [GHz]')
    axes[1,1].set_title('Oscillation Frequency vs L')
    axes[1,1].grid(True, alpha=0.3); axes[1,1].legend()

    plt.tight_layout()
    png = os.path.join(RESULTS_DIR, 'inductor_size_sweep.png')
    plt.savefig(png, dpi=150, bbox_inches='tight')
    print(f"Plot: {png}")

    # Summary
    best = min(valid, key=lambda r: r['p_dc_uW'])
    print(f"\n✓ Minimum power: L={best['L_nH']:.2f}nH → "
          f"P={best['p_dc_uW']:.1f}μW, f={best['f_fft_ghz']:.4f}GHz, "
          f"swing={best['v_swing_V']*1e3:.0f}mV")
    if all(r['v_swing_V'] > 0.200 for r in valid):
        print("  All L values maintain >200mV swing ✓")
    else:
        failing = [r['L_nH'] for r in valid if r['v_swing_V'] < 0.200]
        print(f"  WARNING: swing < 200mV at L = {failing}")
else:
    print("WARNING: No oscillation detected at any L value!")

print("Done.")
