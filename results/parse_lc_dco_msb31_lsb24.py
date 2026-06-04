from pathlib import Path
import cmath
import math
import re


CSV_PATH = Path("/home/whqkrel/rfic_project/results/lc_dco_data.csv")
LOG_PATH = Path("/home/whqkrel/rfic_project/results/lc_dco_msb31_lsb24.log")
NETLIST_PATH = Path("/home/whqkrel/rfic_project/results/lc_dco_top_msb31_lsb24.cir")

text = LOG_PATH.read_text(errors="replace")

samples_total = 0
window_rows = []
with CSV_PATH.open() as f:
    for line in f:
        fields = line.split()
        if len(fields) < 6:
            continue
        samples_total += 1
        # ngspice wrdata emits repeated x-columns:
        # t(outp), v(outp), t(outn), v(outn), t(vs), v(vs)
        row = (float(fields[0]), float(fields[1]), float(fields[5]))
        if 150e-9 <= row[0] <= 200e-9:
            window_rows.append(row)

if not window_rows:
    raise SystemExit("No CSV samples in 150-200ns window")

tw = [row[0] for row in window_rows]
yw = [row[1] for row in window_rows]
vsw = [row[2] for row in window_rows]

v_swing = max(yw) - min(yw)
vs_avg = sum(vsw) / len(vsw)

diffs = [b - a for a, b in zip(tw, tw[1:])]
diffs.sort()
dt = diffs[len(diffs) // 2]
if not math.isfinite(dt) or dt <= 0:
    raise SystemExit(f"Invalid timestep for FFT: {dt}")

def interp(xs, ys, x):
    lo = 0
    hi = len(xs) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if xs[mid] <= x:
            lo = mid
        else:
            hi = mid
    x0 = xs[lo]
    x1 = xs[hi]
    if x1 == x0:
        return ys[lo]
    frac = (x - x0) / (x1 - x0)
    return ys[lo] + frac * (ys[hi] - ys[lo])

def fft(values):
    n = len(values)
    out = [complex(v, 0.0) for v in values]
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            out[i], out[j] = out[j], out[i]
    length = 2
    while length <= n:
        angle = -2.0 * math.pi / length
        wlen = complex(math.cos(angle), math.sin(angle))
        for i in range(0, n, length):
            w = 1.0 + 0.0j
            half = length // 2
            for k in range(i, i + half):
                u = out[k]
                v = out[k + half] * w
                out[k] = u + v
                out[k + half] = u - v
                w *= wlen
        length <<= 1
    return out

n_fft = 1 << int(math.floor(math.log2(len(tw))))
if n_fft < 2:
    raise SystemExit("FFT window too short")
start = tw[0]
stop = tw[-1]
dt_uniform = (stop - start) / n_fft
yu = [interp(tw, yw, start + i * dt_uniform) for i in range(n_fft)]
mean_y = sum(yu) / len(yu)
yu = [v - mean_y for v in yu]
yu = [
    v * (0.5 - 0.5 * math.cos(2.0 * math.pi * i / (n_fft - 1)))
    for i, v in enumerate(yu)
]

spec = fft(yu)
half = n_fft // 2
idx = max(range(1, half + 1), key=lambda i: abs(spec[i]))
fft_dom_freq_hz = idx / (n_fft * dt_uniform)

p_match = re.search(
    r"p_dc_uw\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)",
    text,
)
if not p_match:
    raise SystemExit("Could not parse p_dc_uw from ngspice log")
p_dc_uw = float(p_match.group(1))

log_swing = re.search(
    r"v_swing\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)",
    text,
)
log_vs = re.search(
    r"vs_avg\s*=\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)",
    text,
)

print(f"csv_samples_total={samples_total}")
print(f"window_samples={len(window_rows)}")
print(f"dt_median_s={dt:.12e}")
print(f"fft_samples={n_fft}")
print(f"fft_dt_uniform_s={dt_uniform:.12e}")
print(f"v_swing_v={v_swing:.12e}")
print(f"v_swing_mv={v_swing * 1e3:.9f}")
print(f"p_dc_uw={p_dc_uw:.9f}")
print(f"vs_avg_v={vs_avg:.12e}")
print(f"fft_dom_freq_hz={fft_dom_freq_hz:.12e}")
print(f"fft_dom_freq_ghz={fft_dom_freq_hz / 1e9:.9f}")
print(f"verdict={'PASS' if v_swing > 30e-3 else 'FAIL'}")
if log_swing:
    print(f"log_v_swing_v={float(log_swing.group(1)):.12e}")
if log_vs:
    print(f"log_vs_avg_v={float(log_vs.group(1)):.12e}")

diag_lines = []
for lineno, line in enumerate(text.splitlines(), 1):
    if any(keyword in line.lower() for keyword in ("error", "warning", "fatal")):
        diag_lines.append(f"{lineno}:{line}")

print("diagnostic_keyword_lines_begin")
if diag_lines:
    for line in diag_lines:
        print(line)
else:
    print("NONE")
print("diagnostic_keyword_lines_end")

print("netlist_sanity_begin")
for lineno, line in enumerate(NETLIST_PATH.read_text(errors="replace").splitlines(), 1):
    if any(token in line for token in ("VMSB", "VLSB", "I_tail", "X_tail", ".ic", "wrdata")):
        print(f"{lineno}:{line}")
print("netlist_sanity_end")
