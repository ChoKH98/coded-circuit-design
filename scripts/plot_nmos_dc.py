import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

data_path = os.path.expanduser("~/rfic_project/results/nmos_dc.csv")
data = np.loadtxt(data_path)

vgs = data[:, 0]
ids = -data[:, 1]
ids_uA = ids * 1e6
ids_mA = ids * 1e3

print(f"Data loaded: {len(vgs)} points")
print(f"Vgs range: {vgs[0]:.2f} ~ {vgs[-1]:.2f} V")
print(f"Ids range: {ids[0]:.3e} ~ {ids[-1]:.3e} A")

vth_target = 1e-6
vth_idx = np.argmin(np.abs(ids - vth_target))
vth = vgs[vth_idx]

gm = np.gradient(ids, vgs)
gm_max = np.max(gm)
vgs_gm_max = vgs[np.argmax(gm)]

gm_over_id = np.zeros_like(gm)
nonzero = ids > 1e-15
gm_over_id[nonzero] = gm[nonzero] / ids[nonzero]

valid_sub = (vgs > 0.05) & (vgs < vth) & (ids > 1e-14)
if np.sum(valid_sub) > 5:
    log_ids = np.log10(ids[valid_sub])
    vgs_sub = vgs[valid_sub]
    coeffs = np.polyfit(vgs_sub, log_ids, 1)
    ss = 1000 / coeffs[0]
else:
    ss = float('inf')

print(f"\n{'='*50}")
print(f"  IHP SG13G2 130nm NMOS (W=1um, L=130nm, Vds=0.6V)")
print(f"{'='*50}")
print(f"  Vth:              {vth:.3f} V")
print(f"  Peak gm:          {gm_max*1e3:.3f} mS")
print(f"  Vgs at peak gm:   {vgs_gm_max:.3f} V")
print(f"  SS:                {ss:.1f} mV/dec")
print(f"  Ids @ Vgs=0.3V:   {ids_uA[30]:.4f} uA")
print(f"  Ids @ Vgs=0.6V:   {ids_uA[60]:.2f} uA")
print(f"  Ids @ Vgs=1.2V:   {ids_mA[-1]:.4f} mA")
print(f"  Peak gm/Id:       {np.max(gm_over_id[nonzero]):.1f} V^-1")
print(f"{'='*50}")

fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('IHP SG13G2 130nm NMOS (W=1um, L=130nm, Vds=0.6V)', fontsize=14, fontweight='bold')

ax1 = axes[0, 0]
ax1.plot(vgs, ids_uA, 'b-', linewidth=2)
ax1.axvline(x=vth, color='r', linestyle='--', alpha=0.7, label=f'Vth={vth:.3f}V')
ax1.set_xlabel('Vgs [V]')
ax1.set_ylabel('Ids [uA]')
ax1.set_title('Transfer Characteristics (Linear)')
ax1.grid(True, alpha=0.3)
ax1.legend()

ax2 = axes[0, 1]
valid = ids > 1e-14
ax2.semilogy(vgs[valid], ids[valid], 'r-', linewidth=2)
ax2.axvline(x=vth, color='gray', linestyle='--', alpha=0.7)
ax2.set_xlabel('Vgs [V]')
ax2.set_ylabel('Ids [A]')
ax2.set_title(f'Subthreshold (SS={ss:.1f} mV/dec)')
ax2.grid(True, alpha=0.3, which='both')

ax3 = axes[1, 0]
ax3.plot(vgs, gm * 1e3, 'g-', linewidth=2)
ax3.axvline(x=vgs_gm_max, color='r', linestyle='--', alpha=0.7, label=f'Peak={gm_max*1e3:.3f}mS')
ax3.set_xlabel('Vgs [V]')
ax3.set_ylabel('gm [mS]')
ax3.set_title('Transconductance')
ax3.grid(True, alpha=0.3)
ax3.legend()

ax4 = axes[1, 1]
valid_gmid = (ids > 1e-12) & (vgs > 0.1)
ax4.plot(vgs[valid_gmid], gm_over_id[valid_gmid], 'm-', linewidth=2)
ax4.axhline(y=25, color='gray', linestyle=':', alpha=0.5, label='Weak inv. limit')
ax4.set_xlabel('Vgs [V]')
ax4.set_ylabel('gm/Id [V^-1]')
ax4.set_title('Transconductance Efficiency')
ax4.grid(True, alpha=0.3)
ax4.legend()

plt.tight_layout()
save_path = os.path.expanduser('~/rfic_project/results/nmos_dc_plot.png')
plt.savefig(save_path, dpi=150, bbox_inches='tight')
print(f"\nPlot saved to: {save_path}")
print("Done.")
