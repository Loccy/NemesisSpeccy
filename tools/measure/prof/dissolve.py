"""Length of each stage-end dissolve: frames from the first dz_chunk to the
last of each run of them (LOOP play as pp_feel).  usage: dissolve.py SNA SYM SECS"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys
sys.path.insert(0, os.environ.get('NEM_SPEC', (_NEM + '/spec')))
import emu
from emu import Spectrum, _syms, keys_default
SNA, SYM, SECS = sys.argv[1], sys.argv[2], float(sys.argv[3])
FR = 70908
s = Spectrum(SNA); sy = _syms(SYM)
s.mem.banks[0][sy['m1_75F0'] - 0xC000] = 0xC9
sim = s.sim; R = s.regs; tr = s.tr
DZ = sy['dz_chunk']
hits = []; seen8 = False
for f in range(int(SECS * 50)):
    s.hook(advance=True)
    tr.keyboard = keys_default(f)
    end = s.t0 + (f + 1) * FR
    while True:
        sim.trace(s.pc, DZ, 0, end, 1, None, None, None, None, None); s.pc = R[24]
        if s.pc != DZ or R[25] >= end: break
        hits.append((f, R[25] - s.t0, s.k(0xE061)))
        sim.trace(s.pc, -1, 1, end, 1, None, None, None, None, None); s.pc = R[24]
    s.frame = f + 1
    st = s.k(0xE061)
    if s.k(0xE000) == 5:
        if st == 8: seen8 = True
        if seen8 and st == 1: break
runs = []
for h in hits:
    if runs and h[0] - runs[-1][-1][0] < 100: runs[-1].append(h)
    else: runs.append([h])
tot = 0
for r in runs:
    d = (r[-1][1] - r[0][1]) / FR
    tot += d
    print('stage %d: %3d chunks, %6.1f frames (%.2f s) first to last' % (r[0][2], len(r), d, d / 50))
print('dissolves: %d, %.2f s in all, %.2f s each' % (len(runs), tot / 50, tot / 50 / max(1, len(runs))))
