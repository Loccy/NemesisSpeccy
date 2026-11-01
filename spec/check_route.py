"""The route, the star tiles and the stack (0.101): a run of a build (SNA_DIR,
default this directory), all-stages mode as the
checkers use it (NEM_ALL, NEM_TARGETS from the environment).  Reports: the
stage reached per play second (when each stage starts), the star tiles'
attributes per stage, the deepest stack use (watermark in Konami's stack area
BF80-BFEF, filled with a marker below SP once play starts), and the IM2 table
(AD00-AE00, all 0xAE) checked every 50 frames.
usage: check_route.py SECONDS OUT.json   (with NEM_ALL=1, NEM_TARGETS=1 as for
the checkers)"""
import os, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emu
from emu import Spectrum
D = os.environ.get('SNA_DIR', os.path.dirname(os.path.abspath(__file__))); SECS = float(sys.argv[1]); OUT = sys.argv[2]
s = Spectrum(D + '/nemesis.sna'); sy = emu._syms(D + '/nemesis.sym'); s.syms = sy
if not emu.ALL: s.mem.banks[0][sy['m1_75F0'] - 0xC000] = 0xC9
b2 = s.mem.banks[2]; b7 = s.mem.banks[7]; bC = s.mem.banks[4]
MARK = 0xE5; LO, HI = 0xBF80, 0xBFF0
starts = {}; trans = []; stars = collections.Counter(); im2_bad = []; filled = False; sp_at_fill = None
played = 0; f = 0
while played < SECS * 50:
    s.run_frame(); f += 1
    st = s.k(0xE000)
    if st == 5:
        played += 1
        stage = s.k(0xE061)
        if stage not in starts: starts[stage] = round(played / 50, 1)
        if not trans or trans[-1][1] != stage: trans.append((round(played / 50, 1), stage))
        if not filled:
            sp = s.regs[12]; sp_at_fill = sp
            for a in range(LO, min(sp, HI)): b2[a - 0x8000] = MARK
            filled = True
        if played % 25 == 0:
            for t in range(3):
                for tid in (0xF6, 0xF7):
                    attr = b7[((0xDB + 9 * t + 8) << 8 | tid) - 0xC000]
                    col = bC[0xE800 + t * 0x800 + tid * 8 - 0xC000]
                    stars[(stage, t, '%02X' % tid, '%02X' % col, '%02X' % attr)] += 1
    if f % 50 == 0 and any(b2[a - 0x8000] != 0xAE for a in range(0xAD00, 0xAE01)):
        im2_bad.append(f)
low = next((a for a in range(LO, HI) if b2[a - 0x8000] != MARK), None)
res = {'build': D, 'secs': SECS, 'all': emu.ALL, 'targets': emu.TARGETS, 'stage_starts': starts, 'transitions': trans,
       'stars': [list(k) + [n] for k, n in sorted(stars.items(), key=str)],
       'sp_at_fill': '%04X' % sp_at_fill if sp_at_fill else None, 'deepest_stack_byte_used': '%04X' % low if low else None,
       'stack_marker_intact_from': '%04X' % LO, 'im2_bad_frames': im2_bad[:20]}
json.dump(res, open(OUT, 'w'), indent=1)
print(D.split('/')[-1], 'ALL', emu.ALL, 'TARGETS', emu.TARGETS, 'stage changes (s, stage):', trans)
print('  stack: SP at fill %s, deepest byte used %s (marker region from %04X); IM2 table bad at %d checks' % (res['sp_at_fill'], res['deepest_stack_byte_used'], LO, len(im2_bad)))
