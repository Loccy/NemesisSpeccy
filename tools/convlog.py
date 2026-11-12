"""Every conversion request (convert_cached) in the hatch and boss windows:
its 16 input bytes (pattern, colour), cache hit or miss, and which tile."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, json, collections
sys.path.insert(0, (_NEM + '/spec'))
import emu
from emu import Spectrum
SNA, SYM = sys.argv[1], sys.argv[2]
WIN = {'hatch': (108, 116), 'boss': (175, 183)}
s = Spectrum(SNA); sy = emu._syms(SYM)
s.mem.banks[0][sy['m1_75F0'] - 0xC000] = 0xC9
regs = s.regs; FR = 70908; b2 = s.mem.banks[2]
CC, CT = sy['convert_cached'], sy['convert_tile']
cvp = sy['cv_pat'] - 0x8000
def keys(f):
    kb = [0] * 8
    fire = ((f // 25) % 4 == 0) if s.k(0xE000) != 5 else ((f // 2) % 8 < 4)
    if fire: kb[7] |= 1
    return kb
log = {w: [] for w in WIN}; played = 0
while played < 184 * 50:
    w = next((n for n, (a, b) in WIN.items() if a * 50 <= played < b * 50), None) if s.k(0xE000) == 5 else None
    if w is None:
        s.run_frame(keys)
    else:
        s.hook(advance=True); s.tr.keyboard = keys(s.frame)
        end = s.t0 + (s.frame + 1) * FR; pc = s.pc; pending = None
        while regs[25] < end:
            # stop at either entry point (the page check is implicit: convert_tile only runs in page B)
            s.sim.trace(pc, CC, 0, end, 1, None, None, None, None, None)
            pc = regs[24]
            if pc != CC: break
            inp = bytes(b2[cvp:cvp + 16])
            s.sim.trace(pc, CT, 0, regs[25] + 4000, 1, None, None, None, None, None)   # a miss reaches convert_tile quickly
            miss = regs[24] == CT
            log[w].append((inp.hex(), miss, played))
            pc = regs[24]
            s.sim.trace(pc, -1, 1, end, 1, None, None, None, None, None); pc = regs[24]
        s.pc = pc; s.frame += 1
    if s.k(0xE000) == 5: played += 1
json.dump(log, open(sys.argv[3], 'w'))
for w, L in log.items():
    n = len(L); miss = sum(1 for x in L if x[1]); secs = WIN[w][1] - WIN[w][0]
    print('%s: %d conversion requests (%.0f a second), %d misses (%.0f%%), %d distinct inputs' % (w, n, n / secs, miss, 100 * miss / max(1, n), len({x[0] for x in L})))
