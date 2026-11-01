"""Deterministic speed benchmark: the test build (randomness pinned, sound
once per tick) with the same keys per tick as lockstep_spec.py and an
invulnerable ship, so every build plays the same game tick for tick.
Measures each tick's logic (keyboard, sound, Konami's tick, tile bookkeeping)
and drawing in T-states, then models the pacing (logic overlapping the wait
for the flip; flips at least 2 frames apart).
usage: bench.py [TICKS] [skip]"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, os, re, math, statistics
sys.path.insert(0, NEM_ROOT + '/spec')
from emu import Spectrum
HERE = os.path.dirname(os.path.abspath(__file__))
syms = {}
for l in open(os.path.join(HERE, 'nemesis_test.sym')):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
N = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
SKIP = int(sys.argv[2]) if len(sys.argv) > 2 else 300
FR = 70908
def keys_for_tick(t, started):
    if not started: return (t % 40) < 4
    return t % 8 < 4
spec = Spectrum(os.path.join(HERE, 'nemesis_test.sna'))
spec.mem.banks[0][syms['m1_75F0'] - 0xC000] = 0xC9      # invulnerable
sim = spec.sim; R = spec.regs; tr = spec.tr
LOOP = syms['plat_main.loop']; W = syms['pm_wait']; P = syms['pm_render']; F = syms['pm_flip']
def run(a):
    sim.trace(spec.pc, a, 0, R[25] + FR * 1000, 1, None, None, None, None, None); spec.pc = R[24]
run(LOOP)
rows = []
for i in range(N):
    kb = [0] * 8
    if keys_for_tick(i, spec.k(0xE000) == 5): kb[7] |= 1
    tr.keyboard = kb
    d0 = spec.k(0xE063)
    t0 = R[25]; run(W); t1 = R[25]; run(P); t2 = R[25]; run(F); t3 = R[25]
    sim.trace(spec.pc, -1, 1, R[25] + FR, 1, None, None, None, None, None); spec.pc = R[24]
    run(LOOP)
    if i >= SKIP and spec.k(0xE000) == 5:
        rows.append((t1 - t0, t3 - t2, spec.k(0xE063) != d0))
SOUND = 2 * 3400                # per tick in the real build (the interrupt, twice)
def model(rs):
    Fl = 0; rdone = 0; frames = 0
    for L, Rr, s in rs:
        ld = rdone + L + SOUND
        rd = max(ld, Fl) + Rr; rdone = rd
        nf = math.ceil(max(rd, Fl + 2 * FR) / FR) * FR
        frames += (nf - Fl) // FR; Fl = nf
    return 50.0 * len(rs) / frames
L = [r[0] for r in rows]; D = [r[1] for r in rows]; W2 = [r[0] + r[1] for r in rows]
sc = [r[0] + r[1] for r in rows if r[2]]
print('ticks %d  logic median %d mean %d | draw median %d mean %d | work mean %d, scroll ticks %d mean %d'
      % (len(rows), statistics.median(L), statistics.mean(L), statistics.median(D), statistics.mean(D),
         statistics.mean(W2), len(sc), statistics.mean(sc) if sc else 0))
prev = [False] + [r[2] for r in rows[:-1]]
for name, sel in (('scroll', lambda i: rows[i][2]), ('after', lambda i: prev[i] and not rows[i][2]), ('other', lambda i: not rows[i][2] and not prev[i])):
    ix = [i for i in range(len(rows)) if sel(i)]
    if ix:
        print('  %-7s %4d ticks  logic median %6d  draw median %6d  work mean %6d' % (name, len(ix),
              statistics.median(rows[i][0] for i in ix), statistics.median(rows[i][1] for i in ix),
              statistics.mean(rows[i][0] + rows[i][1] for i in ix)))
print('over 2 frames (with sound): %d%%   modelled ticks/s %.2f' % (100 * sum(1 for w in W2 if w + SOUND > 2 * FR) // len(W2), model(rows)))
