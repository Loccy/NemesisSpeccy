"""Time spent inside named routines (entry to return), per call.
usage: profile.py WORKDIR SECONDS name1,name2,..."""
import sys
sys.path.insert(0, sys.argv[1] + '/tools')
from pathlib import Path
from emu_bench import *
from mini_asm import assemble
from skoolkit.simulator import SP
work = Path(sys.argv[1]); secs = float(sys.argv[2]); names = sys.argv[3].split(',')
_, L = assemble((work / 'build/scroller_expanded.asm').read_text())
for nm in names:
    snap = Snapshot.get(str(work / 'build/nemesis_stage1_scroll_128k.sna')); snap.sp = (snap.sp + 2) % 65536
    sim = from_snapshot(CCMIOSimulator, snap, {}, {'ay': [None]*16}, {'fast_djnz': False, 'fast_ldir': False})
    mem = sim.memory; mem.out7ffd(snap.out7ffd)
    tr = Tracer(sim, snap.border, snap.out7ffd, snap.outfffd, list(snap.ay), snap.outfe, False); sim.set_tracer(tr)
    regs = sim.registers; pc = snap.pc; end = regs[25] + int(secs*50*FRAME); a = L[nm]; v = []
    while regs[25] < end:
        tr.keyboard = keys_for(regs[25] // FRAME)
        sim.trace(pc, a, 0, end, 1, None, None, None, None, None); pc = regs[24]
        if pc != a: break
        t0 = regs[25]; sp = regs[SP]; ret = mem[sp] | mem[sp+1] << 8
        while True:
            sim.trace(pc, ret, 0, end, 1, None, None, None, None, None); pc = regs[24]
            if pc != ret or regs[SP] == sp + 2: break
        v.append(regs[25] - t0)
    v.sort(); n = len(v)
    if n: print(f'{nm:18s} calls {n:5d}  median {v[n//2]:7,}  p90 {v[int(n*.9)]:7,}  max {v[-1]:7,}  total/s {sum(v)//secs:9,.0f}')
