"""Every full conversion (convert_tile) over the all-stages route (NEM_ALL,
NEM_TARGETS): its 16 input bytes, play second, stage, cost in T-states."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, json
sys.path.insert(0, (_NEM + '/spec'))
import emu
from emu import Spectrum, keys_default, FRAME
D = sys.argv[1]; SECS = float(sys.argv[2]); OUT = sys.argv[3]
s = Spectrum(D + '/nemesis.sna'); sy = emu._syms(D + '/nemesis.sym'); s.syms = sy
regs = s.regs; CT = sy['convert_tile']; P, C = sy['cv_pat'], sy['cv_col']
log = []; played = 0
while played < SECS * 50:
    s.hook(advance=True); s.tr.keyboard = keys_default(s.frame)
    end = s.t0 + (s.frame + 1) * FRAME; pc = s.pc
    while True:
        s.sim.trace(pc, CT, 0, end, 1, None, None, None, None, None)
        pc = regs[24]
        if pc != CT or regs[25] >= end: break
        if s.tr.out7ffd & 7 != 3:        # same address in another page: step past it
            s.sim.trace(pc, -1, 0, regs[25] + 1, 1, None, None, None, None, None); pc = regs[24]; continue
        inp = bytes(s.mem[P + i] for i in range(8)) + bytes(s.mem[C + i] for i in range(8))
        sp = regs[12]; ret = s.mem[sp] | s.mem[sp + 1] << 8; t0 = regs[25]
        s.sim.trace(pc, ret, 0, t0 + FRAME * 50, 1, None, None, None, None, None)
        pc = regs[24]
        log.append((inp.hex(), round(played / 50, 2), s.k(0xE061), regs[25] - t0))
        if regs[25] >= end: break
    if regs[25] < end:
        s.sim.trace(pc, -1, 0, end, 1, None, None, None, None, None); pc = regs[24]
    s.pc = pc; s.frame += 1
    if s.k(0xE000) == 5: played += 1
    if s.frame % 15000 == 0: print('second %d stage %d conversions %d' % (played // 50, s.k(0xE061), len(log)), flush=True)
json.dump(log, open(OUT, 'w'))
print('done', len(log))
