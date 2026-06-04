"""Temperature sweep for NMOS LC-DCO (Phase 3).

Corners: -40, 0, 27, 85°C at MSB=0, LSB=0 (nominal 2.4GHz point).
Reports f_osc, V_swing, P_dc, V(vs) vs temperature.
"""

import os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
from sweep_msb import freq_from_csv

BASE_DIR = "/home/whqkrel/rfic_project"
TOP_CIR  = f"{BASE_DIR}/circuits/lc_dco_nmos_top.cir"
TMP_DIR  = f"{BASE_DIR}/results"
OUT_TXT  = f"{BASE_DIR}/results/sweep_temp_summary.txt"

TEMPS = [-40, 0, 27, 85]


def make_netlist(temp):
    with open(TOP_CIR) as f:
        lines = f.readlines()

    out = []
    temp_inserted = False
    for line in lines:
        # Insert .temp after first .lib line
        if line.strip().startswith(".lib") and not temp_inserted:
            out.append(line)
            out.append(f".temp {temp}\n")
            temp_inserted = True
            continue
        # Update wrdata path
        if "wrdata" in line:
            tag = f"{'m' if temp < 0 else 'p'}{abs(temp):03d}"
            line = f"wrdata {TMP_DIR}/sweep_temp_{tag}.csv v(outp) v(outn) v(vs)\n"
        out.append(line)

    tag = f"{'m' if temp < 0 else 'p'}{abs(temp):03d}"
    tmp_path = f"{TMP_DIR}/_sweep_tmp_temp_{tag}.cir"
    with open(tmp_path, "w") as f:
        f.writelines(out)
    return tmp_path, tag


def parse_output(stdout):
    result = {"v_swing_mv": None, "p_uw": None, "vs_v": None}
    m = re.search(r"v_swing\s*=\s*([\d.eE+\-]+)", stdout, re.IGNORECASE)
    if m:
        result["v_swing_mv"] = float(m.group(1)) * 1e3
    m = re.search(r"p_dc_uw\s*=\s*([\d.eE+\-]+)", stdout, re.IGNORECASE)
    if m:
        result["p_uw"] = float(m.group(1))
    m = re.search(r"vs_avg\s*=\s*([\d.eE+\-]+)", stdout, re.IGNORECASE)
    if m:
        result["vs_v"] = float(m.group(1))
    return result


def freq_from_temp_csv(tag):
    csv = f"{TMP_DIR}/sweep_temp_{tag}.csv"
    if not os.path.exists(csv):
        return None
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
    if len(times) < 10:
        return None
    tw = [(t, v) for t, v in zip(times, vout) if 150e-9 <= t <= 300e-9]
    if len(tw) < 10:
        return None
    ts, vs = zip(*tw)
    vmean = sum(vs) / len(vs)
    crossings = []
    for i in range(1, len(ts)):
        if vs[i-1] < vmean <= vs[i]:
            frac = (vmean - vs[i-1]) / (vs[i] - vs[i-1])
            crossings.append(ts[i-1] + frac*(ts[i]-ts[i-1]))
    if len(crossings) < 2:
        return None
    periods = [crossings[i+1]-crossings[i] for i in range(len(crossings)-1)]
    return 1.0 / (sum(periods)/len(periods)) / 1e9


def main():
    rows = []
    for temp in TEMPS:
        print(f"Running T={temp:+4d}°C ...", end=" ", flush=True)
        cir, tag = make_netlist(temp)
        proc = subprocess.run(["ngspice", "-b", cir],
                              capture_output=True, text=True, timeout=300)
        out = proc.stdout + proc.stderr
        r = parse_output(out)
        f = freq_from_temp_csv(tag)
        status = "PASS" if (r["v_swing_mv"] and r["v_swing_mv"] > 100) else "FAIL"
        f_s  = f"{f:.4f}" if f else "---"
        sw_s = f"{r['v_swing_mv']:.1f}" if r["v_swing_mv"] else "---"
        p_s  = f"{r['p_uw']:.1f}" if r["p_uw"] else "---"
        vs_s = f"{r['vs_v']:.3f}" if r["vs_v"] else "---"
        print(f"f={f_s}GHz Vswing={sw_s}mV P={p_s}uW Vs={vs_s}V [{status}]")
        rows.append((temp, f_s, sw_s, p_s, vs_s, status))

    header = f"{'Temp(C)':>8} {'f_osc(GHz)':>12} {'V_swing(mV)':>12} {'P_dc(uW)':>10} {'V(vs)(V)':>9} {'STATUS':>6}"
    sep = "-" * 62
    lines = [header, sep]
    for t, f, sw, p, vs, st in rows:
        lines.append(f"{t:>8} {f:>12} {sw:>12} {p:>10} {vs:>9} {st:>6}")
    table = "\n".join(lines)
    print("\n" + table)
    with open(OUT_TXT, "w") as f:
        f.write(table + "\n")
    print(f"\nSaved to {OUT_TXT}")


if __name__ == "__main__":
    main()
