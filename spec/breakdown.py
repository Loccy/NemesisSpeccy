"""Per-tick cost of the Spectrum build: Konami's tick, tile bookkeeping,
rendering (and inside it: erase, cells, sprites), waiting.  The sound
interrupt is counted in whatever it interrupted.

usage: breakdown.py SECONDS [skip_seconds]
"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re, os
sys.path.insert(0, NEM_ROOT + '/spec')
from emu import Spectrum, keys_default
HERE = NEM_ROOT + '/spec'
syms = {}
for l in open(os.path.join(HERE, 'nemesis.sym')):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
secs = float(sys.argv[1]); skip = float(sys.argv[2]) if len(sys.argv) > 2 else 0
m = Spectrum()
for f in range(int(skip * 50)): m.run_frame()
L0 = syms['plat_main.loop']
rf = syms['render_frame']
# points: tick start, tick end (tick_tiles call), render start, erase done, cells done, sprites done (pop af), flip call, loop
lst = open(os.path.join(HERE, 'nemesis.lst')).read()
pts = [syms['pm_tick'], syms['pm_tiles'], syms['pm_wait'], syms['pm_render']]
# inside render_frame: the calls to erase_sprites, draw_cells, draw_sprites, and the final pop af
def call_site(target):
    for line in lst.split('\n'):
        mm = re.match(r'\s*\d+\+?\s+([0-9A-F]{4})\s+CD ([0-9A-F]{2}) ([0-9A-F]{2})', line)
        if mm and int(mm.group(3) + mm.group(2), 16) == syms[target] and syms['render_frame'] <= int(mm.group(1), 16) < syms['render_frame'] + 80:
            return int(mm.group(1), 16)
    raise KeyError(target)
pts += [syms['rf_erased'], syms['rf_cells'], syms['rf_sprites'], syms['pm_flip']]
names = ['tick', 'tiles', 'wait', 'erase', 'cells', 'sprites', 'rest']
sim = m.sim; regs = m.regs; FR = 70908
end = regs[25] + int(secs * 50 * FR)
rows = []; k = 0; ts = []
while regs[25] < end:
    m.tr.keyboard = keys_default(regs[25] // FR)
    sim.trace(m.pc, pts[k], 0, end, 1, None, None, None, None, None); m.pc = regs[24]
    if m.pc != pts[k]: break
    ts.append(regs[25])
    if k == len(pts) - 1:
        rows.append([ts[i + 1] - ts[i] for i in range(len(pts) - 1)] + [m.k(0xE000)])
        ts = []
    k = (k + 1) % len(pts)
    if k == 0: ts = []
    if k == 1 and not ts: pass
play = [r for r in rows if r[-1] == 5]
print('ticks measured', len(rows), 'in play', len(play))
for i, nm in enumerate(names):
    v = sorted(r[i] for r in play) or [0]
    print('%-8s median %7d  p90 %7d  max %7d' % (nm, v[len(v) // 2], v[int(len(v) * .9)], v[-1]))
tot = sorted(sum(r[:7]) - r[2] for r in play) or [0]
mean = sum(tot) / max(1, len(tot))
print('work     median %7d  p90 %7d  max %7d  mean %7d  (2 frames = %d)' % (tot[len(tot) // 2], tot[int(len(tot) * .9)], tot[-1], mean, 2 * FR))
heavy = [r for r in play if sum(r[:7]) - r[2] > 2 * FR]
print('ticks over 2 frames: %d of %d' % (len(heavy), len(play)))
for i, nm in enumerate(names):
    v = sorted(r[i] for r in heavy) or [0]
    print('  %-8s median %7d  mean %7d' % (nm, v[len(v) // 2], sum(v) / len(v)))
import collections
h = collections.Counter(min(int((sum(r[:7]) - r[2]) / 10000), 40) for r in play)
print('work histogram (10k T bins):', ' '.join('%d:%d' % (k * 10, v) for k, v in sorted(h.items())))
