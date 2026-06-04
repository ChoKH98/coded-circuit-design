csv = "/home/whqkrel/rfic_project/results/postlayout_nmos_data.csv"
times, vout = [], []
with open(csv) as f:
    for line in f:
        parts = line.split()
        if len(parts) >= 2:
            try: times.append(float(parts[0])); vout.append(float(parts[1]))
            except ValueError: pass
tw = [(t,v) for t,v in zip(times,vout) if 150e-9<=t<=300e-9]
ts, vs = zip(*tw)
vmean = sum(vs)/len(vs)
crossings = []
for i in range(1,len(ts)):
    if vs[i-1]<vmean<=vs[i]:
        frac=(vmean-vs[i-1])/(vs[i]-vs[i-1])
        crossings.append(ts[i-1]+frac*(ts[i]-ts[i-1]))
periods=[crossings[i+1]-crossings[i] for i in range(len(crossings)-1)]
f=1.0/(sum(periods)/len(periods))/1e9
print(f"Post-layout f_osc = {f:.4f} GHz")
print(f"Schematic  f_osc = 2.4029 GHz")
print(f"Frequency shift  = {(f-2.4029)*1000:+.1f} MHz ({(f/2.4029-1)*100:+.2f}%)")
