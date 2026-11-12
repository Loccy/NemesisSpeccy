import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, collections
sys.path.insert(0, (_NEM + '/spec'))
import emu
from emu import Spectrum, keys_default, FRAME
D = sys.argv[1]; SECS = int(sys.argv[2])
s = Spectrum(D + '/nemesis.sna'); sy = emu._syms(D + '/nemesis.sym'); s.syms = sy; regs = s.regs
STUB = sy['far_m3_A6C0']
inv = {v: k for k, v in sy.items() if k.startswith('m2_') or k.startswith('m3_') or k.startswith('m1_')}
played = 0; runs = []; cur = None
while played < SECS * 50:
    s.hook(advance=True); s.tr.keyboard = keys_default(s.frame)
    end = s.t0 + (s.frame + 1) * FRAME; pc = s.pc; hit = False
    while regs[25] < end:
        s.sim.trace(pc, STUB, 0, end, 1, None, None, None, None, None); pc = regs[24]
        if pc != STUB: break
        sp = regs[12]; ret = s.mem[sp] | s.mem[sp + 1] << 8
        hit = True
        if cur is None:
            cur = {'start': played / 50, 'stage': s.k(0xE061), 'ret': '%04X' % ret, 'calls': 0, 'ticks0': s.k(0xE003)}
        cur['calls'] += 1
        s.sim.trace(pc, -1, 0, regs[25] + 1, 1, None, None, None, None, None); pc = regs[24]
    s.pc = pc; s.frame += 1
    if s.k(0xE000) == 5: played += 1
    if cur is not None and not hit and s.frame % 1 == 0:
        cur.setdefault('quiet', 0); cur['quiet'] += 1
        if cur['quiet'] > 100:
            cur['end'] = played / 50 - 2; runs.append(cur); print(cur, flush=True); cur = None
    elif cur is not None: cur['quiet'] = 0
print('runs', len(runs))
