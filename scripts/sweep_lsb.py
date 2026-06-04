"""LSB fine-tuning sweep for NMOS LC-DCO (Phase 3).

MSB=0 fixed. LSB codes: 0,4,8,12,16,20,24,28,31.
Reports f_osc, V_swing, P_dc, V(vs) to verify fine-tuning resolution.
"""

import os, re, subprocess, sys

BASE_DIR = "/home/whqkrel/rfic_project"
TOP_CIR  = f"{BASE_DIR}/circuits/lc_dco_nmos_top.cir"
TMP_DIR  = f"{BASE_DIR}/results"
OUT_TXT  = f"{BASE_DIR}/results/sweep_lsb_summary.txt"

LSB_CODES = [0, 4, 8, 12, 16, 20, 24, 28, 31]

V_BASE     = 0.470
V_STEP_LSB = 0.00250


def bits(code):
    return [(code >> i) & 1 for i in range(4, -1, -1)]


def make_netlist(code):
    b4, b3, b2, b1, b0 = bits(code)
    v_ref = max(V_BASE - V_STEP_LSB * code, 0.25)

    with open(TOP_CIR) as f:
        lines = f.readlines()

    out = []
    for line in lines:
        if re.match(r"VLSB4\s", line):
            line = f"VLSB4 lsb4 0 DC {b4}\n"
        elif re.match(r"VLSB3\s", line):
            line = f"VLSB3 lsb3 0 DC {b3}\n"
        elif re.match(r"VLSB2\s", line):
            line = f"VLSB2 lsb2 0 DC {b2}\n"
        elif re.match(r"VLSB1\s", line):
            line = f"VLSB1 lsb1 0 DC {b1}\n"
        elif re.match(r"VLSB0\s", line):
            line = f"VLSB0 lsb0 0 DC {b0}\n"
        elif line.strip().startswith(".ic "):
            line = f".ic V(outp)=0.850 V(outn)=0.650 V(vs)={v_ref:.4f} V(X_tail.v_ctrl)=0.37\n"
        elif "wrdata" in line:
            line = f"wrdata {TMP_DIR}/sweep_lsb{code:02d}.csv v(outp) v(outn) v(vs)\n"
        out.append(line)

    tmp_path = f"{TMP_DIR}/_sweep_tmp_lsb{code:02d}.cir"
    with open(tmp_path, "w") as f:
        f.writelines(out)
    return tmp_path


def freq_from_csv(code):
    csv = f"{TMP_DIR}/sweep_lsb{code:02d}.csv"
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


def parse_output(stdout):
    r = {"v_swing_mv": None, "p_uw": None, "vs_v": None}
    m = re.search(r"v_swing\s*=\s*([\d.eE+\-]+)", stdout, re.IGNORECASE)
    if m:
        r["v_swing_mv"] = float(m.group(1)) * 1e3
    m = re.search(r"p_dc_uw\s*=\s*([\d.eE+\-]+)", stdout, re.IGNORECASE)
    if m:
        r["p_uw"] = float(m.group(1))
    m = re.search(r"vs_avg\s*=\s*([\d.eE+\-]+)", stdout, re.IGNORECASE)
    if m:
        r["vs_v"] = float(m.group(1))
    return r


def main():
    rows = []
    for code in LSB_CODES:
        print(f"Running LSB={code:2d} ...", end=" ", flush=True)
        cir = make_netlist(code)
        proc = subprocess.run(["ngspice", "-b", cir],
                              capture_output=True, text=True, timeout=300)
        r = parse_output(proc.stdout + proc.stderr)
        f = freq_from_csv(code)
        status = "PASS" if (r["v_swing_mv"] and r["v_swing_mv"] > 100) else "FAIL"
        f_s  = f"{f:.4f}" if f else "---"
        sw_s = f"{r['v_swing_mv']:.1f}" if r["v_swing_mv"] else "---"
        p_s  = f"{r['p_uw']:.1f}" if r["p_uw"] else "---"
        vs_s = f"{r['vs_v']:.3f}" if r["vs_v"] else "---"
        print(f"f={f_s}GHz Vswing={sw_s}mV P={p_s}uW Vs={vs_s}V [{status}]")
        rows.append((code, f_s, sw_s, p_s, vs_s, status))

    header = f"{'LSB':>4} {'f_osc(GHz)':>12} {'V_swing(mV)':>12} {'P_dc(uW)':>10} {'V(vs)(V)':>9} {'STATUS':>6}"
    sep = "-" * 58
    lines = [header, sep]
    for c, f, sw, p, vs, st in rows:
        lines.append(f"{c:>4} {f:>12} {sw:>12} {p:>10} {vs:>9} {st:>6}")
    table = "\n".join(lines)
    print("\n" + table)
    with open(OUT_TXT, "w") as f:
        f.write(table + "\n")
    print(f"\nSaved to {OUT_TXT}")


if __name__ == "__main__":
    main()
