"""Log each tick's logic and drawing cost (T-states) and the frames between
the flips the build actually made, on the test build, for the pacing model.
Workloads: 'bench' (lockstep keys, invulnerable ship firing on a rhythm) or
'attract' (fire held 12 ticks in 50, the ship can die).
usage: pacelog.py DIR WORKLOAD TICKS OUT.json"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, os, re, json
D, WL, N, OUT = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
sys.path.insert(0, NEM_ROOT + '/spec')
from emu import Spectrum
syms = {}
for l in open(os.path.join(D, 'nemesis_test.sym')):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
FR = 70908
spec = Spectrum(os.path.join(D, 'nemesis_test.sna'))
if WL == 'bench': spec.mem.banks[0][syms['m1_75F0'] - 0xC000] = 0xC9
sim = spec.sim; R = spec.regs; tr = spec.tr
LOOP = syms['plat_main.loop']; W = syms['pm_wait']; P = syms['pm_render']; F = syms['pm_flip']
def run(a):
    sim.trace(spec.pc, a, 0, R[25] + FR * 1000, 1, None, None, None, None, None); spec.pc = R[24]
def fire(i, started):
    if WL == 'bench': return (i % 8 < 4) if started else ((i % 40) < 4)
    return (i % 50) < 12
run(LOOP); rows = []; t0 = R[25]
for i in range(N):
    kb = [0] * 8
    started = spec.k(0xE000) == 5
    if fire(i, started): kb[7] |= 1
    tr.keyboard = kb
    d0 = spec.k(0xE063)
    a = R[25]; run(W); b = R[25]; run(P); c = R[25]; run(F); d = R[25]
    sim.trace(spec.pc, -1, 1, R[25] + FR, 1, None, None, None, None, None); spec.pc = R[24]
    run(LOOP)
    rows.append([b - a, d - c, int(spec.k(0xE063) != d0), int(spec.k(0xE000) == 5), (c - t0) // FR])
json.dump(rows, open(OUT, 'w'))
print('logged', len(rows))
