"""Input lag on a Spectrum build (SNA_DIR): in stage 1 play, up or down is
pressed at the start of a frame, and the lag is counted to the frame whose
displayed screen first shows the ship moved, plus the time for the beam to
reach the ship's line (63 + y of 312 lines).  Trials at varied phases.
usage: lag.py TRIALS"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, random, statistics
sys.path.insert(0, (_NEM + '/spec'))
import emu
from emu import Spectrum, keys_default
D = os.environ.get('SNA_DIR', (_NEM + '/spec')); N = int(sys.argv[1])
s = Spectrum(D + '/nemesis.sna'); syms = emu._syms(D + '/nemesis.sym'); s.syms = syms
s.mem.banks[0][syms['m1_75F0'] - 0xC000] = 0xC9
P = syms['pm_render']; sim = s.sim; R = s.regs; FR = 70908; SA = 0x2F00 + 0xC80
drawn = {0: None, 1: None}
cur = [0] * 8
def frame():
    s.tr.keyboard = cur
    end = s.t0 + (s.frame + 1) * FR
    while True:
        sim.trace(s.pc, P, 0, end, 1, None, None, None, None, None); s.pc = R[24]
        if s.pc != P: break
        hidden = 0 if s.tr.out7ffd & 8 else 1        # screen 1 shown -> draws screen 0
        drawn[hidden] = s.mem.banks[2][SA]            # the ship's sprite Y as drawn
        sim.trace(s.pc, -1, 1, end, 1, None, None, None, None, None); s.pc = R[24]
    s.frame += 1
    return drawn[1 if s.tr.out7ffd & 8 else 0]        # Y shown now
played = 0
while played < 40 * 50:
    cur = keys_default(s.frame) if s.k(0xE000) != 5 else [0] * 8
    frame()
    if s.k(0xE000) == 5: played += 1
random.seed(int(os.environ.get("SEED","7"))); lags = []
for t in range(N):
    for i in range(random.randint(10, 40)):            # settle, varied phase
        cur = [0] * 8; frame()
    y0 = frame()
    up = s.k(0xE204) > 0x40
    cur = [0, 0, 1, 0, 0, 0, 0, 0] if up else [0, 1, 0, 0, 0, 0, 0, 0]
    for k in range(40):
        y = frame()
        if y is not None and y0 is not None and y != y0:
            lags.append(k + (63 + y) / 312); break
    cur = [0] * 8
lags.sort(); print("worst:", ["%.1f" % x for x in lags[-5:]]); print('%s: %d presses, lag in frames mean %.1f, median %.1f, min %.1f, max %.1f' % (D, len(lags), statistics.mean(lags), statistics.median(lags), min(lags), max(lags)))
