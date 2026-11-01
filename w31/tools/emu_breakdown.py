import sys
sys.path.insert(0, sys.argv[1] + '/tools')
from pathlib import Path
from emu_bench import *
from mini_asm import assemble
work = Path(sys.argv[1]); secs = float(sys.argv[2])
_, L = assemble((work / 'build/scroller_expanded.asm').read_text())
S = L['main_loop.sprites']
pts = [L['main_loop'], L['main_loop'] + 7, S, S + 3, S + 6]
names = ['logic', 'scroll', 'erase', 'draw']
snap = Snapshot.get(str(work / 'build/nemesis_stage1_scroll_128k.sna')); snap.sp = (snap.sp + 2) % 65536
sim = from_snapshot(CCMIOSimulator, snap, {}, {'ay': [None]*16}, {'fast_djnz': False, 'fast_ldir': False})
mem = sim.memory; mem.out7ffd(snap.out7ffd)
tr = Tracer(sim, snap.border, snap.out7ffd, snap.outfffd, list(snap.ay), snap.outfe, False); sim.set_tracer(tr)
regs = sim.registers; pc = snap.pc
end = regs[25] + int(secs*50*FRAME); rows = []; k = 0; ts = []
def nact():
    b = mem.banks[2]; base = L['enemy_projections'] - 0x8000
    return sum(1 for i in range(12) if b[base + 4*i])
while regs[25] < end:
    tr.keyboard = keys_for(regs[25] // FRAME)
    sim.trace(pc, pts[k], 0, end, 1, None, None, None, None, None); pc = regs[24]
    if pc != pts[k]: break
    if k == 0: ts = [regs[25]]
    else: ts.append(regs[25])
    if k == 4:
        rows.append(tuple(ts[i+1] - ts[i] for i in range(4)) + (nact(),))
    k = (k + 1) % 5
rows.sort(key=lambda r: -sum(r[:4]))
import statistics
for i, nm in enumerate(names):
    v = sorted(r[i] for r in rows)
    print(f'{nm:7s} median {v[len(v)//2]:7,}  p90 {v[int(len(v)*.9)]:7,}  max {v[-1]:7,}')
print('worst 8 ticks (logic, scroll, erase, draw, visible enemies):')
for r in rows[:8]: print('  ', r)
