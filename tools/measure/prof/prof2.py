"""Exact profile, whole run: address-level totals and per-second function-level T-states.
usage: prof2.py SNA SYM FRAMES OUT.pkl  (NEM_ALL=1)"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, os, time, pickle, collections
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from labels import Labels
from emu import Spectrum, _syms, keys_default
SNA, SYM, N, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
LB = Labels(SNA, SYM); func = LB.func
s = Spectrum(SNA); sy = _syms(SYM)
s.mem.banks[0][sy['m1_75F0'] - 0xC000] = 0xC9
sim = s.sim; R = s.regs; tr = s.tr; FR = 70908
MOVE = os.environ.get('MOVE') == '1'
def KEYS(f):
    kb = keys_default(f)
    if MOVE:
        ph = (f // 40) % 8
        if ph in (0, 5): kb[2] |= 1          # Q up
        elif ph in (2, 7): kb[1] |= 1        # A down
        if ph in (1, 2): kb[5] |= 1          # P right
        elif ph in (4, 5): kb[5] |= 2        # O left
    return kb
acc = collections.defaultdict(int); cnt = collections.defaultdict(int); sec = collections.defaultdict(int)
PT = sy['pm_tick']; PR = sy['pm_render']
st = [0, R[25], 0, 0]
def tf(pc, i, t0):
    k = st[0]
    sec[k] += t0 - st[1]
    if pc >= 0xC000: k = pc | (tr.out7ffd & 7) << 16
    else:
        k = pc
        if pc == PT: st[2] += 1
        elif pc == PR: st[3] += 1
    st[0] = k; st[1] = t0
    cnt[k] += 1
df = lambda pc: None
t = time.time(); SECS = []
for f in range(N):
    s.hook(advance=True); tr.keyboard = KEYS(s.frame)
    sim.trace(s.pc, -1, 0, s.t0 + (s.frame + 1) * FR, 1, None, None, tr.keyboard, df, tf); s.pc = R[24]; s.frame += 1
    if s.frame % 50 == 0:
        fs = collections.defaultdict(int)
        for k, v in sec.items(): fs[func(k)] += v; acc[k] += v
        SECS.append((s.frame, s.k(0xE000), s.k(0xE061), s.k(0xE063) | s.k(0xE064) << 8, st[2], st[3], dict(fs)))
        sec.clear(); st[2] = 0; st[3] = 0
        if s.frame % 5000 == 0: print('frame %d stage %d  %.0f s' % (s.frame, s.k(0xE061), time.time() - t), flush=True)
    if s.k(0xE000) == 5 and s.k(0xE061) == 1 and f > 80000: break
pickle.dump(dict(acc=dict(acc), cnt=dict(cnt), SECS=SECS, sna=SNA, sym=SYM), open(OUT, 'wb'))
print('done %d frames in %.0f s' % (s.frame, time.time() - t))
