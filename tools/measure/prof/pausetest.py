"""Pause and resume in play (H), for a build: the scroll must stop while paused and go on after.  pausetest.py SNA SYM"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys
sys.path.insert(0, os.environ.get('NEM_SPEC', (_NEM + '/spec')))
import emu
from emu import Spectrum, _syms, keys_default
s = Spectrum(sys.argv[1]); sy = _syms(sys.argv[2])
s.mem.banks[0][sy['m1_75F0'] - 0xC000] = 0xC9
FR = 70908; sim = s.sim; R = s.regs; tr = s.tr
log = []; start = None
def dist(): return s.k(0xE063) | s.k(0xE064) << 8
for f in range(2600):
    kb = keys_default(f)
    if start is None and s.k(0xE000) == 5 and dist() > 0x20: start = f
    if start is not None:
        if start + 100 <= f < start + 104: kb[6] |= 0x10          # H: pause
        if start + 500 <= f < start + 504: kb[6] |= 0x10          # H: resume
    s.hook(advance=True); tr.keyboard = kb
    end = s.t0 + (f + 1) * FR
    sim.trace(s.pc, -1, 0, end, 1, None, None, None, None, None); s.pc = R[24]
    s.frame = f + 1
    if start is not None: log.append((f - start, dist(), s.k(0xE10C) & 1, s.k(0xE003)))
def at(n): return log[n]
print('play from frame', start)
for n in (0, 99, 110, 200, 300, 499, 510, 600, 800):
    if n < len(log): print('  frame +%3d: distance %04X  paused flag %d  tick counter %02X' % at(n))
d = [x[1] for x in log]
print('distance while paused (+120..+495) constant:', len(set(d[120:496])) == 1, '; moved before:', d[99] > d[0], '; moved after resume:', d[800] > d[505] if len(d) > 800 else None)
