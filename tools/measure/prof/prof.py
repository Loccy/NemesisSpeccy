"""Exact profile of the 128K build: every instruction's T-states by address
(and page), executions by address, and per-tick records.
usage: prof.py SNA SYM SKIP_FRAMES FRAMES OUT.pkl   (NEM_ALL=1 for the cheat)"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, os, time, pickle, collections
sys.path.insert(0, os.environ.get('NEM_SPEC', (_NEM + '/spec')))
from emu import Spectrum, _syms, keys_default
SNA, SYM, SKIP, N, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
s = Spectrum(SNA); sy = _syms(SYM)
s.mem.banks[0][sy['m1_75F0'] - 0xC000] = 0xC9
sim = s.sim; R = s.regs; tr = s.tr; FR = 70908
KEYS = keys_default
if os.environ.get('MOVE') == '1':
    def KEYS(f):
        kb = keys_default(f)
        ph = (f // 60) % 4
        if ph == 0: kb[2] |= 1          # Q up
        elif ph == 2: kb[1] |= 1        # A down
        return kb
for f in range(SKIP):
    s.hook(advance=True); tr.keyboard = KEYS(s.frame)
    sim.trace(s.pc, -1, 0, s.t0 + (s.frame + 1) * FR, 1, None, None, None, None, None); s.pc = R[24]; s.frame += 1
print('skipped to frame', s.frame, 'state', s.k(0xE000), 'stage', s.k(0xE061), 'dist %04X' % (s.k(0xE063) | s.k(0xE064) << 8), flush=True)
acc = collections.defaultdict(int); cnt = collections.defaultdict(int)
EV = {sy[k]: k for k in ('pm_tick', 'pm_tiles', 'pm_wait', 'pm_render', 'pm_flip', 'rf_erased', 'rf_cells', 'rf_sprites', 'isr')}
EV[sy['plat_main.loop']] = 'loop'
events = []
st = [0, R[25]]
def tf(pc, i, t0):
    k = st[0]
    acc[k] += t0 - st[1]
    if pc >= 0xC000: k = pc | (tr.out7ffd & 7) << 16
    else: k = pc
    st[0] = k; st[1] = t0
    cnt[k] += 1
    if pc in EV: events.append((EV[pc], t0))
df = lambda pc: None
t = time.time(); meta = []
for f in range(N):
    s.hook(advance=True); tr.keyboard = KEYS(s.frame)
    sim.trace(s.pc, -1, 0, s.t0 + (s.frame + 1) * FR, 1, None, None, tr.keyboard, df, tf); s.pc = R[24]; s.frame += 1
    meta.append((s.k(0xE000), s.k(0xE061), s.k(0xE063) | s.k(0xE064) << 8, s.k(0xE003), R[25]))
    events.append(('frame', R[25]))
print('profiled %d frames in %.0f s; end stage %d dist %04X' % (N, time.time() - t, s.k(0xE061), s.k(0xE063) | s.k(0xE064) << 8))
pickle.dump(dict(acc=dict(acc), cnt=dict(cnt), events=events, meta=meta, sna=SNA, sym=SYM), open(OUT, 'wb'))
