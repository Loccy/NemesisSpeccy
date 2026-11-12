import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, collections
sys.path.insert(0, (_NEM + '/spec'))
import emu
from emu import Spectrum, keys_default, FRAME
D = sys.argv[1]; A, B = int(sys.argv[2]), int(sys.argv[3])
s = Spectrum(D + '/nemesis.sna'); sy = emu._syms(D + '/nemesis.sym'); s.syms = sy; regs = s.regs
ET, FULL, REFIT = sy['ensure_tile'], sy['ensure_tile.full'], sy['ensure_tile.refit']
played = 0; cnt = collections.defaultdict(collections.Counter)
while played < B * 50:
    if played < A * 50 or s.k(0xE000) != 5:
        s.run_frame()
    else:
        s.hook(advance=True); s.tr.keyboard = keys_default(s.frame)
        end = s.t0 + (s.frame + 1) * FRAME; pc = s.pc; sec = played // 50
        while regs[25] < end:
            s.sim.trace(pc, ET, 0, end, 1, None, None, None, None, None); pc = regs[24]
            if pc != ET: break
            t = regs[25]
            s.sim.trace(pc, FULL, 0, t + 300, 1, None, None, None, None, None); pc = regs[24]
            if pc == FULL: cnt[sec]['full'] += 1; continue
            s.sim.trace(pc, REFIT, 0, t + 6000, 1, None, None, None, None, None); pc = regs[24]
            cnt[sec]['refit' if pc == REFIT else 'other'] += 1
        s.pc = pc; s.frame += 1
    if s.k(0xE000) == 5: played += 1
for sec in sorted(cnt): print(sec, dict(cnt[sec]))
