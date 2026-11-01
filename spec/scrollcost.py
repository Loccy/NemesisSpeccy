"""Per-tick work split by whether the map scrolled this tick (Konami's
distance E063 moved) or last tick (the other screen catching up).
usage: scrollcost.py SECONDS [skip]"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re, os
sys.path.insert(0, NEM_ROOT + '/spec')
from emu import Spectrum, keys_default
syms = {}
for l in open(NEM_ROOT + '/spec/nemesis.sym'):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
secs = float(sys.argv[1]); skip = float(sys.argv[2]) if len(sys.argv) > 2 else 20
m = Spectrum(); sim = m.sim; regs = m.regs; FR = 70908
for f in range(int(skip * 50)): m.run_frame()
end = regs[25] + int(secs * 50 * FR)
pts = [syms['pm_tick'], syms['pm_wait'], syms['pm_render'], syms['rf_cells'], syms['pm_flip']]
NC = syms['nm_count'] - 0x8000; b2 = m.mem.banks[2]
rows = []
while regs[25] < end:
    m.tr.keyboard = keys_default(regs[25] // FR)
    t = []
    for p in pts:
        sim.trace(m.pc, p, 0, end, 1, None, None, None, None, None); m.pc = regs[24]; t.append(regs[25])
        if p == pts[0]: d0 = m.k(0xE063) | m.k(0xE064) << 8
        if p == pts[1]: full = (m.k(0xE063) | m.k(0xE064) << 8) != d0     # the map moved a column this tick
    if regs[25] >= end: break
    rows.append((full, t[1] - t[0], t[3] - t[2], t[4] - t[2], (t[1] - t[0]) + (t[4] - t[2])))
def summ(name, rs):
    if not rs: return
    w = sorted(r[4] for r in rs); c = sorted(r[2] for r in rs); k = sorted(r[1] for r in rs)
    print('%-26s %4d ticks  work median %6d mean %6d  | tick %6d  cells(+erase) %6d' % (name, len(rs), w[len(w)//2], sum(w)/len(w), k[len(k)//2], c[len(c)//2]))
summ('scroll tick', [r for i, r in enumerate(rows) if r[0]])
summ('tick after a scroll', [r for i, r in enumerate(rows) if i and rows[i-1][0] and not r[0]])
summ('other ticks', [r for i, r in enumerate(rows) if not r[0] and not (i and rows[i-1][0])])
summ('all', rows)
