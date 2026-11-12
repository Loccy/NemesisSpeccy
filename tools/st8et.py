import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, collections
sys.path.insert(0, (_NEM + '/spec'))
import emu
from emu import Spectrum, keys_default, FRAME
D = sys.argv[1]; A, B = int(sys.argv[2]), int(sys.argv[3])
s = Spectrum(D + '/nemesis.sna'); sy = emu._syms(D + '/nemesis.sym'); s.syms = sy; regs = s.regs
ET = sy['ensure_tile']; CD = sy['tile_cdirty']
played = 0; cnt = collections.defaultdict(collections.Counter); ex = {}
while played < B * 50:
    if played < A * 50 or s.k(0xE000) != 5:
        s.run_frame()
    else:
        s.hook(advance=True); s.tr.keyboard = keys_default(s.frame)
        end = s.t0 + (s.frame + 1) * FRAME; pc = s.pc; sec = played // 50
        while regs[25] < end:
            s.sim.trace(pc, ET, 0, end, 1, None, None, None, None, None); pc = regs[24]
            if pc != ET: break
            d, e = regs[4], regs[5]   # D third, E id
            i = d * 32 + (e >> 3); bit = 1 << (e & 7)
            c = s.mem[CD + i] & bit; p = s.mem[CD + 0x80 + i] & bit
            sp = regs[12]; caller = s.mem[sp] | s.mem[sp + 1] << 8
            k = ('C' if c else '') + ('P' if p else '') or 'none'
            cnt[sec][k] += 1; cnt[sec]['from %04X' % caller] += 1
            ex.setdefault(sec, []).append('%d:%02X' % (d, e))
            s.sim.trace(pc, -1, 0, regs[25] + 1, 1, None, None, None, None, None); pc = regs[24]
        s.pc = pc; s.frame += 1
    if s.k(0xE000) == 5: played += 1
for sec in sorted(cnt): print(sec, dict(cnt[sec]), ' '.join(ex.get(sec, [])[:10]))
