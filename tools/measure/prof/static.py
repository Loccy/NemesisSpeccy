"""How many sprites are unchanged (Y, X, pattern, colour) from the same screen's previous picture."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, os, collections
os.environ['NEM_ALL'] = '1'
sys.path.insert(0, (_NEM + '/spec'))
from emu import Spectrum, _syms, keys_default
SNA = (_NEM + '/spec/nemesis.sna'); sy = _syms(SNA[:-4] + '.sym')
MOVE = os.environ.get('MOVE') == '1'
def KEYS(f):
    kb = keys_default(f)
    if MOVE:
        ph = (f // 40) % 8
        if ph in (0, 5): kb[2] |= 1
        elif ph in (2, 7): kb[1] |= 1
        if ph in (1, 2): kb[5] |= 1
        elif ph in (4, 5): kb[5] |= 2
    return kb
s = Spectrum(SNA); sim = s.sim; R = s.regs; tr = s.tr; FR = 70908; STOP = sy['pm_render']
prev = {0: set(), 8: set()}; C = collections.Counter()
for f in range(int(sys.argv[1])):
    s.hook(advance=True); tr.keyboard = KEYS(s.frame)
    end = s.t0 + (s.frame + 1) * FR
    while R[25] < end:
        sim.trace(s.pc, STOP, 0, end, 1, None, None, None, None, None); s.pc = R[24]
        if s.pc == STOP and R[25] < end:
            cur = set(); ship = None
            for i in range(32):
                y = s.k(0xEC80 + 4 * i)
                if y == 0xD0: break
                x, p, c = s.k(0xEC81 + 4 * i), s.k(0xEC82 + 4 * i), s.k(0xEC83 + 4 * i)
                if (y + 1) & 0xFF >= 177 or not (c & 15): continue
                if p < 24 and (p & 4): continue
                cur.add((y, x, p & 0xFC, c))
            scr = (tr.out7ffd & 8) ^ 8
            if s.k(0xE000) == 5:
                C['sprites'] += len(cur); C['static'] += len(cur & prev[scr]); C['pictures'] += 1
                if any(p == 0 or p == 8 or p == 16 for y, x, p, c in cur & prev[scr]): C['ship_static'] += 1
            prev[scr] = cur
            sim.trace(s.pc, -1, 1, end, 1, None, None, None, None, None); s.pc = R[24]
    s.frame += 1
    if s.k(0xE000) == 5 and s.k(0xE061) == 1 and f > 80000: break
print(dict(C), 'static %.1f%%' % (100 * C['static'] / C['sprites']), 'ship static in %.0f%% of pictures' % (100 * C['ship_static'] / C['pictures']))
