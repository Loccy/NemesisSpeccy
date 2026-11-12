"""Ticks in each second of play over the loop (NEM_ALL=1): how the speed is spread.  persec.py SNA SYM"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, collections
sys.path.insert(0, os.environ.get('NEM_SPEC', (_NEM + '/spec')))
import emu
from emu import Spectrum, _syms, keys_default
s = Spectrum(sys.argv[1]); sy = _syms(sys.argv[2])
s.mem.banks[0][sy['m1_75F0'] - 0xC000] = 0xC9
FR = 70908; sim = s.sim; R = s.regs; tr = s.tr
last = s.k(0xE003); tot = 0; secs = []; cur = 0; n = 0; seen8 = False
for f in range(90000):
    s.hook(advance=True); tr.keyboard = keys_default(f)
    end = s.t0 + (f + 1) * FR
    sim.trace(s.pc, -1, 0, end, 1, None, None, None, None, None); s.pc = R[24]
    s.frame = f + 1
    e = s.k(0xE003); d = (e - last) & 255; last = e
    if s.k(0xE000) == 5:
        cur += d; n += 1
        if n == 50: secs.append((cur, s.k(0xE061))); cur = 0; n = 0
        st = s.k(0xE061)
        if st == 8: seen8 = True
        if seen8 and st == 1: break
    else: cur = 0; n = 0
t = sorted(x[0] for x in secs); N = len(t)
print('%d seconds in play, mean %.2f ticks/s' % (N, sum(t) / N))
print('slowest second %d, 5%% %d, 25%% %d, median %d, 75%% %d, 95%% %d, fastest %d' % (t[0], t[N // 20], t[N // 4], t[N // 2], t[3 * N // 4], t[19 * N // 20], t[-1]))
for lim in (25, 27, 30, 33, 40): print('  seconds above %d ticks: %4.1f%%' % (lim, 100 * sum(1 for x in t if x > lim) / N))
h = collections.Counter(min(x // 2 * 2, 48) for x in t)
print('  histogram (ticks in the second: seconds):', ' '.join('%d-%d: %d' % (k, k + 1, h[k]) for k in sorted(h)))
