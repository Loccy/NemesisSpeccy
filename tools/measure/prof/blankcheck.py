"""Every time draw_cells takes its blank-cell path, character 0 of that third must be eight zero rows in the tile set.  blankcheck.py SNA SYM [FRAMES]"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys
sys.path.insert(0, os.environ.get('NEM_SPEC', (_NEM + '/spec')))
import emu
from emu import Spectrum, _syms, keys_default
s = Spectrum(sys.argv[1]); sy = _syms(sys.argv[2]); FRAMES = int(sys.argv[3]) if len(sys.argv) > 3 else 90000
s.mem.banks[0][sy['m1_75F0'] - 0xC000] = 0xC9
FR = 70908; sim = s.sim; R = s.regs; tr = s.tr; B = s.mem.banks
P = sy['draw_cells.blank']; DT = sy['dc_third'] - 0x8000
n = bad = 0; seen8 = False; states = set()
for f in range(FRAMES):
    s.hook(advance=True); tr.keyboard = keys_default(f)
    end = s.t0 + (f + 1) * FR
    while True:
        sim.trace(s.pc, P, 0, end, 1, None, None, None, None, None); s.pc = R[24]
        if s.pc != P or R[25] >= end: break
        t = B[2][DT]; n += 1; states.add(s.k(0xE000))
        rows = [B[7][((0xDB + 9 * t + r) << 8) - 0xC000] for r in range(8)]
        if any(rows):
            bad += 1
            if bad <= 5: print('frame %d state %d stage %d third %d: character 0 is' % (f, s.k(0xE000), s.k(0xE061), t), rows)
        sim.trace(s.pc, -1, 1, end, 1, None, None, None, None, None); s.pc = R[24]
    s.frame = f + 1
    st = s.k(0xE061)
    if s.k(0xE000) == 5:
        if st == 8: seen8 = True
        if seen8 and st == 1 and f % 50 == 0 and s.k(0xE063) > 0x40: break
print('blank cells drawn: %d, with character 0 not blank: %d; game states seen: %s; frames %d' % (n, bad, sorted(states), f + 1))
