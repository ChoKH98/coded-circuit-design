"""Check injection locking: compare free-running vs locked frequency."""

csv = "/home/whqkrel/rfic_project/results/il_pll_nmos_data.csv"

times, vout = [], []
with open(csv) as f:
    for line in f:
        parts = line.split()
        if len(parts) >= 2:
            try:
                times.append(float(parts[0]))
                vout.append(float(parts[1]))
            except ValueError:
                pass


def freq_in_window(t_start, t_end):
    tw = [(t, v) for t, v in zip(times, vout) if t_start <= t <= t_end]
    if len(tw) < 10:
        return None
    ts, vs = zip(*tw)
    vmean = sum(vs) / len(vs)
    crossings = []
    for i in range(1, len(ts)):
        if vs[i - 1] < vmean <= vs[i]:
            frac = (vmean - vs[i - 1]) / (vs[i] - vs[i - 1])
            crossings.append(ts[i - 1] + frac * (ts[i] - ts[i - 1]))
    if len(crossings) < 2:
        return None
    periods = [crossings[i + 1] - crossings[i] for i in range(len(crossings) - 1)]
    return 1.0 / (sum(periods) / len(periods)) / 1e9


f_early = freq_in_window(100e-9, 150e-9)
f_late  = freq_in_window(400e-9, 500e-9)
f_inj   = 50 * 48e6 / 1e9  # = 2.4000 GHz

print(f"Free-running  (100-150ns): {f_early:.5f} GHz")
print(f"Post-inject   (400-500ns): {f_late:.5f} GHz")
print(f"Injection target          : {f_inj:.5f} GHz")
if f_early and f_late:
    shift = (f_late - f_early) * 1000
    pull  = (f_late - f_early) / (f_inj - f_early) * 100 if f_inj != f_early else 0
    print(f"Frequency shift           : {shift:+.2f} MHz")
    print(f"Pull toward injection     : {pull:.1f}%")
    locked = abs(f_late - f_inj) < abs(f_early - f_inj)
    print(f"Verdict: {'LOCKED (frequency pulled toward injection)' if locked else 'NOT LOCKED (no pull detected)'}")
