"""T-states (with contention) from main_loop to wait_and_flip, per tick.
usage: tickcost.py WORKDIR SECONDS"""
import sys
sys.path.insert(0, sys.argv[1] + '/tools')
from pathlib import Path
from emu_bench import *
from mini_asm import assemble
work = Path(sys.argv[1]); secs = float(sys.argv[2])
_, L = assemble((work / 'build/scroller_expanded.asm').read_text())
A, B = L['main_loop'], L['wait_and_flip']
snap = Snapshot.get(str(work / 'build/nemesis_stage1_scroll_128k.sna')); snap.sp = (snap.sp + 2) % 65536
sim = from_snapshot(CCMIOSimulator, snap, {}, {'ay': [None]*16}, {'fast_djnz': False, 'fast_ldir': False})
mem = sim.memory; mem.out7ffd(snap.out7ffd)
tr = Tracer(sim, snap.border, snap.out7ffd, snap.outfffd, list(snap.ay), snap.outfe, False); sim.set_tracer(tr)
regs = sim.registers; pc = snap.pc
end = regs[25] + int(secs*50*FRAME); costs = []; t0 = None; target = A; per_sec = {}
while regs[25] < end:
    tr.keyboard = keys_for(regs[25] // FRAME)
    sim.trace(pc, target, 0, end, 1, None, None, None, None, None); pc = regs[24]
    if pc == A: t0 = regs[25]; target = B
    elif pc == B and t0 is not None:
        c = regs[25] - t0; costs.append(c); s = regs[25] // (50*FRAME)
        per_sec[s] = max(per_sec.get(s, 0), c); target = A
costs.sort(); n = len(costs)
print(f'ticks {n}: median {costs[n//2]:,}  p90 {costs[int(n*.9)]:,}  p99 {costs[int(n*.99)]:,}  max {costs[-1]:,}  (budget {2*FRAME:,})')
print("over budget:", sum(c>2*FRAME for c in costs), "of", n)
print("max per 10s:", [max(per_sec.get(s,0) for s in range(i,i+10)) for i in range(0,int(secs),10)])
