"""MSB tuning-range sweep for NMOS LC-DCO (Phase 3).

Sweeps MSB codes with LSB=0, runs ngspice for each, reports f_osc, V_swing,
P_dc, V(vs). Saves summary to results/sweep_msb_summary.txt.
"""

import os
import re
import subprocess
import sys

BASE_DIR = "/home/whqkrel/rfic_project"
TOP_CIR  = f"{BASE_DIR}/circuits/lc_dco_nmos_top.cir"
TMP_DIR  = f"{BASE_DIR}/results"
OUT_TXT  = f"{BASE_DIR}/results/sweep_msb_summary.txt"

MSB_CODES = [0, 4, 8, 12, 16, 20, 24, 28, 31]

V_BASE     = 0.470
V_STEP_MSB = 0.00400  # per unit weight


def bits(code):
    return [(code >> i) & 1 for i in range(4, -1, -1)]  # [b4,b3,b2,b1,b0]


def make_netlist(code):
    b4, b3, b2, b1, b0 = bits(code)
    v_ref = V_BASE - V_STEP_MSB * code
    v_ref = max(v_ref, 0.25)  # clamp to reasonable minimum

    with open(TOP_CIR) as f:
        lines = f.readlines()

    out = []
    for line in lines:
        # Replace VMSB/VLSB source lines
        if re.match(r"VMSB4\s", line):
            line = f"VMSB4 msb4 0 DC {b4}\n"
        elif re.match(r"VMSB3\s", line):
            line = f"VMSB3 msb3 0 DC {b3}\n"
        elif re.match(r"VMSB2\s", line):
            line = f"VMSB2 msb2 0 DC {b2}\n"
        elif re.match(r"VMSB1\s", line):
            line = f"VMSB1 msb1 0 DC {b1}\n"
        elif re.match(r"VMSB0\s", line):
            line = f"VMSB0 msb0 0 DC {b0}\n"
        elif re.match(r"VLSB[0-4]\s", line):
            bit = int(re.match(r"VLSB(\d)", line).group(1))
            line = f"VLSB{bit} lsb{bit} 0 DC 0\n"
        # Update .ic to match expected V(vs) = V_ref for this code
        elif line.strip().startswith(".ic "):
            line = f".ic V(outp)=0.850 V(outn)=0.650 V(vs)={v_ref:.4f} V(X_tail.v_ctrl)=0.37\n"
        # (no SPICE freq measurement — computed from CSV after sim)
        # Update wrdata output path
        elif "wrdata" in line:
            line = f"wrdata {TMP_DIR}/sweep_msb{code:02d}.csv v(outp) v(outn) v(vs)\n"
        out.append(line)

    tmp_path = f"{TMP_DIR}/_sweep_tmp_msb{code:02d}.cir"
    with open(tmp_path, "w") as f:
        f.writelines(out)
    return tmp_path


def freq_from_csv(code):
    """Compute oscillation frequency from zero-crossings of v(outp) in saved CSV."""
    csv_path = f"{TMP_DIR}/sweep_msb{code:02d}.csv"
    if not os.path.exists(csv_path):
        return None
    times, vout = [], []
    with open(csv_path) as f:
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
    # Filter to measurement window 150n–300n
    t_start, t_end = 150e-9, 300e-9
    tw = [(t, v) for t, v in zip(times, vout) if t_start <= t <= t_end]
    if len(tw) < 10:
        return None
    ts, vs = zip(*tw)
    vmean = sum(vs) / len(vs)
    # Count rising zero-crossings relative to mean
    crossings = []
    for i in range(1, len(ts)):
        if vs[i - 1] < vmean <= vs[i]:
            # linear interpolate crossing time
            frac = (vmean - vs[i - 1]) / (vs[i] - vs[i - 1])
            crossings.append(ts[i - 1] + frac * (ts[i] - ts[i - 1]))
    if len(crossings) < 2:
        return None
    periods = [crossings[i + 1] - crossings[i] for i in range(len(crossings) - 1)]
    avg_period = sum(periods) / len(periods)
    return 1.0 / avg_period / 1e9


def parse_output(stdout, code):
    result = {"msb": code, "f_ghz": None, "v_swing_mv": None, "p_uw": None, "vs_v": None}

    # V_swing
    m = re.search(r"v_swing\s*=\s*([\d.eE+\-]+)", stdout, re.IGNORECASE)
    if m:
        result["v_swing_mv"] = float(m.group(1)) * 1e3

    # P_dc
    m = re.search(r"p_dc_uw\s*=\s*([\d.eE+\-]+)", stdout, re.IGNORECASE)
    if m:
        result["p_uw"] = float(m.group(1))

    # V(vs)
    m = re.search(r"vs_avg\s*=\s*([\d.eE+\-]+)", stdout, re.IGNORECASE)
    if m:
        result["vs_v"] = float(m.group(1))

    return result


def run_sim(cir_path):
    try:
        proc = subprocess.run(
            ["ngspice", "-b", cir_path],
            capture_output=True, text=True, timeout=300
        )
        return proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except FileNotFoundError:
        return "ERROR: ngspice not found"


def main():
    rows = []
    for code in MSB_CODES:
        print(f"Running MSB={code:2d} ...", end=" ", flush=True)
        cir = make_netlist(code)
        out = run_sim(cir)
        r = parse_output(out, code)
        r["f_ghz"] = freq_from_csv(code)

        status = "PASS" if (r["v_swing_mv"] and r["v_swing_mv"] > 100) else "FAIL"
        f_str  = f"{r['f_ghz']:.4f}" if r["f_ghz"] else "---"
        sw_str = f"{r['v_swing_mv']:.1f}" if r["v_swing_mv"] else "---"
        p_str  = f"{r['p_uw']:.1f}" if r["p_uw"] else "---"
        vs_str = f"{r['vs_v']:.3f}" if r["vs_v"] else "---"

        print(f"f={f_str}GHz  Vswing={sw_str}mV  P={p_str}uW  Vs={vs_str}V  [{status}]")
        rows.append((code, f_str, sw_str, p_str, vs_str, status))

    header = f"{'MSB':>4} {'f_osc(GHz)':>12} {'V_swing(mV)':>12} {'P_dc(uW)':>10} {'V(vs)(V)':>9} {'STATUS':>6}"
    sep    = "-" * len(header)
    lines  = [header, sep]
    for code, f, sw, p, vs, st in rows:
        lines.append(f"{code:>4} {f:>12} {sw:>12} {p:>10} {vs:>9} {st:>6}")

    table = "\n".join(lines)
    print("\n" + table)

    os.makedirs(os.path.dirname(OUT_TXT), exist_ok=True)
    with open(OUT_TXT, "w") as f:
        f.write(table + "\n")
    print(f"\nSaved to {OUT_TXT}")


if __name__ == "__main__":
    main()
