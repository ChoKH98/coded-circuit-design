import sys
sys.path.insert(0, '/home/whqkrel/rfic_project/scripts')
from sweep_msb import freq_from_csv, TMP_DIR

codes = [0, 4, 8, 12, 16, 20, 24, 28, 31]

summary = {}
with open(f'{TMP_DIR}/sweep_msb_summary.txt') as f:
    for line in f:
        parts = line.split()
        if parts and parts[0].isdigit():
            summary[int(parts[0])] = parts

header = f"{'MSB':>4} {'f_osc(GHz)':>12} {'V_swing(mV)':>12} {'P_dc(uW)':>10} {'V(vs)(V)':>9} {'STATUS':>6}"
sep = "-" * 60
rows = []
for code in codes:
    f = freq_from_csv(code)
    f_str = f"{f:.4f}" if f else "---"
    s = summary.get(code, [str(code), "---", "---", "---", "---", "?"])
    rows.append(f"{code:>4} {f_str:>12} {s[2]:>12} {s[3]:>10} {s[4]:>9} {s[5]:>6}")

print(header)
print(sep)
for r in rows:
    print(r)

with open(f'{TMP_DIR}/sweep_msb_summary.txt', 'w') as f:
    f.write(header + "\n" + sep + "\n" + "\n".join(rows) + "\n")
print("\nUpdated sweep_msb_summary.txt")
