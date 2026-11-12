import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, collections
sys.path.insert(0, (_NEM + '/spec'))
import emu
from emu import Spectrum, keys_default, FRAME
D = sys.argv[1]; A, B = int(sys.argv[2]), int(sys.argv[3])
s = Spectrum(D + '/nemesis.sna'); sy = emu._syms(D + '/nemesis.sym'); s.syms = sy; regs = s.regs
MK = 0x8147; VBM = sy['vb_map']; b7 = s.mem.banks[7]; SS = sy['seen_stage'] - 0xC000
tiles = {}; played = 0; cnt = collections.defaultdict(collections.Counter); prev = None
while played < B * 50:
    if played < A * 50 or s.k(0xE000) != 5:
        s.run_frame()
    else:
        s.hook(advance=True); s.tr.keyboard = keys_default(s.frame)
        end = s.t0 + (s.frame + 1) * FRAME; pc = s.pc; sec = played // 50
        while regs[25] < end:
            s.sim.trace(pc, MK, 0, end, 1, None, None, None, None, None); pc = regs[24]
            if pc != MK: break
            de = regs[4] << 8 | regs[5]; cnt[sec]['byte colour writes'] += 1; tiles.setdefault(sec, set()).add(de >> 3)
            s.sim.trace(pc, -1, 0, regs[25] + 1, 1, None, None, None, None, None); pc = regs[24]
        s.pc = pc; s.frame += 1
        v = b7[SS]
        if prev is not None and v != prev: cnt[sec]['stage seen %d->%d' % (prev, v)] += 1
        prev = v
        cnt[sec]['E061=%d E1A0=%d' % (s.k(0xE061), s.k(0xE1A0))] += 0
    if s.k(0xE000) == 5: played += 1
for sec in sorted(cnt): print(sec, cnt[sec]["byte colour writes"], "tiles", len(tiles.get(sec, ())), sorted("%03X" % t for t in tiles.get(sec, ()))[:12])
