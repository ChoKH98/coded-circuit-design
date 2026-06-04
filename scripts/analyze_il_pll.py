import numpy as np

data = np.loadtxt('/home/whqkrel/rfic_project/results/il_pll_detuned.csv')
t = data[:,0]; v = data[:,1]

def fft_freq(t, v, t0, t1):
    mask = (t>=t0)&(t<=t1)
    tw,vw = t[mask], v[mask]
    if len(tw)<50: return 0.0, 0.0
    vac = vw - vw.mean()
    sw = vw.max()-vw.min()
    N = len(vac); dt = (tw[-1]-tw[0])/(N-1)
    spec = np.abs(np.fft.rfft(vac*np.hanning(N)))
    freq = np.fft.rfftfreq(N,d=dt)
    valid = freq>1e9
    pk = freq[valid][np.argmax(spec[valid])]
    return pk/1e9, sw

wins = [
    ('  0- 50ns startup  ',   0,      50e-9),
    (' 50-150ns free-run ',  50e-9,  150e-9),
    ('150-200ns inj-start', 150e-9,  200e-9),
    ('200-300ns locking  ', 200e-9,  300e-9),
    ('300-400ns settling ', 300e-9,  400e-9),
    ('400-500ns steady   ', 400e-9,  500e-9),
]
print('  Window                f[GHz]   Swing[mV]')
print('  -------------------------------------------')
freqs = []
for lbl,t0,t1 in wins:
    f,sw = fft_freq(t,v,t0,t1)
    freqs.append(f)
    print('  %s   %.4f    %.1f' % (lbl, f, sw*1e3))

f_free = freqs[1]
f_late = freqs[5]
pull_MHz = (f_late - f_free)*1000
locked = abs(f_late - 2.4000) < 0.005

print('')
print('  Free-running : %.4f GHz  (LSB=23)' % f_free)
print('  After inj    : %.4f GHz' % f_late)
print('  Pull         : %+.1f MHz' % pull_MHz)
print('  Target       : 2.4000 GHz')
if locked:
    print('  Result       : LOCKED to 2.4GHz')
else:
    dist = abs(f_late-2.4)*1000
    print('  Result       : %.1f MHz from target (partial pull)' % dist)
