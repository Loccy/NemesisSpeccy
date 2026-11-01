"""PC-sampling profile of the ticks where the map scrolls (Konami's distance
E063 moved), split into the tick phase and the render phase.
usage: scrollprof.py SECONDS [skip]"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re, collections, bisect, os
sys.path.insert(0, NEM_ROOT + '/spec')
os.environ['PHASE'] = 'none'
src = open(NEM_ROOT + '/spec/sample_prof.py').read().split("secs = float")[0]
exec(src)
from emu import Spectrum, keys_default
secs = float(sys.argv[1]); skip = float(sys.argv[2]) if len(sys.argv) > 2 else 20
m = Spectrum(); sim = m.sim; regs = m.regs; FR = 70908
for f in range(int(skip * 50)): m.run_frame()
P0 = syms['pm_tick']; P1 = syms['pm_wait']; P2 = syms['pm_render']; P3 = syms['pm_flip']
end = regs[25] + int(secs * 50 * FR); SL = 397
ts = collections.Counter(); rs = collections.Counter(); n = 0
while regs[25] < end:
    m.tr.keyboard = keys_default(regs[25] // FR)
    sim.trace(m.pc, P0, 0, end, 1, None, None, None, None, None); m.pc = regs[24]
    d0 = m.k(0xE063); a = collections.Counter(); b = collections.Counter()
    while True:
        sim.trace(m.pc, P1, 0, regs[25] + SL, 1, None, None, None, None, None); m.pc = regs[24]
        if m.pc == P1 or regs[25] >= end: break
        a[where(m.pc, m.tr.out7ffd & 7)] += 1
    scrolled = m.k(0xE063) != d0
    sim.trace(m.pc, P2, 0, end, 1, None, None, None, None, None); m.pc = regs[24]
    while True:
        sim.trace(m.pc, P3, 0, regs[25] + SL, 1, None, None, None, None, None); m.pc = regs[24]
        if m.pc == P3 or regs[25] >= end: break
        b[where(m.pc, m.tr.out7ffd & 7)] += 1
    if scrolled: ts.update(a); rs.update(b); n += 1
print('scroll ticks', n)
for name, c in (('TICK phase', ts), ('RENDER phase', rs)):
    print(name, 'mean T per scroll tick %.0f' % (sum(c.values()) * SL / max(1, n)))
    agg = collections.Counter()
    for k, v in c.items(): agg[k if re.match(r'\d+:', k) else k.split('.')[0]] += v
    for k, v in agg.most_common(14): print('   %6.0f T  %s' % (v * SL / max(1, n), k))
