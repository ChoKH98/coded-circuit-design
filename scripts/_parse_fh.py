"""Parse FastHenry Zc.mat output and extract L, Q vs frequency."""
import re, math

ZC_FILE = "/home/whqkrel/rfic_project/Zc.mat"
OUT_FILE = "/home/whqkrel/rfic_project/em/results/inductor_LQ.txt"

freqs, Ls, Rs = [], [], []
with open(ZC_FILE) as f:
    freq = None
    for line in f:
        m = re.search(r"frequency\s*=\s*([\d.e+\-]+)", line)
        if m:
            freq = float(m.group(1))
        m = re.search(r"([\d.e+\-]+)\s+\+\s*([\d.e+\-]+)j", line)
        if m and freq:
            R = float(m.group(1))
            X = float(m.group(2))
            L_nH = X / (2 * math.pi * freq) * 1e9
            # Q: substrate losses not modeled → air-core only, note limitation
            freqs.append(freq / 1e9)
            Ls.append(L_nH)
            Rs.append(R)
            freq = None

# Print table
header = f"{'f(GHz)':>10} {'L_half(nH)':>12} {'R_dc(Ω)':>10}"
sep = "-" * 36
rows = [header, sep]
target_idx = None
for i, (f, L, R) in enumerate(zip(freqs, Ls, Rs)):
    rows.append(f"{f:>10.4f} {L:>12.4f} {R:>10.6f}")
    if abs(f - 2.4) < 0.1:
        target_idx = i

print("\n".join(rows))

if target_idx is not None:
    f24 = freqs[target_idx]
    L24 = Ls[target_idx]
    R24 = Rs[target_idx]
    print(f"\n--- At f ≈ 2.4 GHz (f={f24:.4f} GHz) ---")
    print(f"  L_half = {L24:.3f} nH  (schematic assumed: 2.000 nH)")
    print(f"  Rs_dc  = {R24:.6f} Ω   (air-core, substrate losses NOT included)")
    print(f"  Q_aircore = ωL/R = {2*math.pi*f24*1e9*L24*1e-9/R24:.0f}  (unrealistic - no substrate loss)")
    print(f"  NOTE: For physical Q (~15-25), openEMS simulation with substrate needed")
    print(f"  NOTE: L_half={L24:.2f}nH vs sim 2.00nH — geometry difference from actual layout")

with open(OUT_FILE, "w") as f:
    f.write("\n".join(rows) + "\n")
print(f"\nSaved to {OUT_FILE}")
