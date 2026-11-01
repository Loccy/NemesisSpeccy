"""PC-sampling profile on the bench workload (see bench.py): the logic or
drawing phase of scroll ticks (WHAT=scroll) or other ticks (WHAT=other).
usage: benchprof.py TICKS [logic|draw] [scroll|other]"""
import sys, os, re, collections, bisect
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emu import Spectrum
HERE = os.path.dirname(os.path.abspath(__file__))
syms = {}
for l in open(os.path.join(HERE, 'nemesis_test.sym')):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
N = int(sys.argv[1]); PH = sys.argv[2]; WHAT = sys.argv[3]
fixed = sorted((v, k) for k, v in syms.items() if v < 0xC000 and '.' not in k); fk = [v for v, k in fixed]
paged = sorted((v, k) for k, v in syms.items() if v >= 0xC000 and '.' not in k); pk = [v for v, k in paged]
def where(pc, page):
    if pc < 0xC000:
        i = bisect.bisect_right(fk, pc) - 1; return fixed[i][1] if i >= 0 else '?'
    i = bisect.bisect_right(pk, pc) - 1
    return 'p%d:%s' % (page, paged[i][1]) if page in (0, 4) else 'page%d' % page
FR = 70908; SL = 397
spec = Spectrum(os.path.join(HERE, 'nemesis_test.sna'))
spec.mem.banks[0][syms['m1_75F0'] - 0xC000] = 0xC9
sim = spec.sim; R = spec.regs; tr = spec.tr
LOOP = syms['plat_main.loop']; W = syms['pm_wait']; P = syms['pm_render']; F = syms['pm_flip']
def run(a):
    sim.trace(spec.pc, a, 0, R[25] + FR * 1000, 1, None, None, None, None, None); spec.pc = R[24]
def sample(stop, c):
    while True:
        sim.trace(spec.pc, stop, 0, R[25] + SL, 1, None, None, None, None, None); spec.pc = R[24]
        if spec.pc == stop: return
        c[where(spec.pc, spec.tr.out7ffd & 7)] += 1
run(LOOP); tot = collections.Counter(); n = 0
for i in range(N):
    kb = [0] * 8
    started = spec.k(0xE000) == 5
    if (i % 8 < 4) if started else ((i % 40) < 4): kb[7] |= 1
    tr.keyboard = kb
    d0 = spec.k(0xE063); a = collections.Counter(); b = collections.Counter()
    sample(W, a); run(P); sample(F, b)
    sim.trace(spec.pc, -1, 1, R[25] + FR, 1, None, None, None, None, None); spec.pc = R[24]
    run(LOOP)
    s = spec.k(0xE063) != d0
    if i >= 300 and spec.k(0xE000) == 5 and s == (WHAT == 'scroll'):
        tot.update(a if PH == 'logic' else b); n += 1
print('%d ticks; mean T per tick in %s' % (n, PH))
for k, v in tot.most_common(22): print('  %7d  %s' % (v * SL // n, k))
