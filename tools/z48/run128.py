"""Run the 128K build (a .sna) in SkoolKit's 128K simulator from a chosen
stage, for comparing screens with the 48K version (z48tap.py).

usage: run128.py SNA STAGE SECONDS PREFIX [NAMETABLE]
  STAGE      poked into Konami's stage (E061) when play first starts (state 4)
  SAFE=1     the ship cannot die (1:75F0, in page 0 at C000+15FC, a bare ret);
             without it a game over comes, and its screen is saved 5, 30
             and 80 frames in (PREFIX_goN.png)
  SHOTF=a:b  a screenshot every second frame from frame a to b (PREFIX_fN.png)
  NAMETABLE  (hex) print the 22 rows of the name table's copy at the end
Konami's RAM is at AF00 in page 2 on the 128K (E000 = AF00).  Prints each
change of Konami's state (E000) and stage (E061)."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'spec'))
from emu_bench import scr_png, keys_for, FRAME
from skoolkit.snapshot import Snapshot
from skoolkit.simutils import from_snapshot
from skoolkit import CCMIOSimulator
from skoolkit.trace import Tracer
STAGE = int(sys.argv[2]); SECS = float(sys.argv[3]); PRE = sys.argv[4]
SHOTF = [int(x) for x in os.environ["SHOTF"].split(":")] if os.environ.get("SHOTF") else None
snap = Snapshot.get(sys.argv[1])
if snap.type == 'SNA' and len(snap.tail) == 0xC000: snap.sp = (snap.sp + 2) % 65536
sim = from_snapshot(CCMIOSimulator, snap, {}, {'ay': [None] * 16}, {'fast_djnz': False, 'fast_ldir': False})
mem = sim.memory; mem.out7ffd(snap.out7ffd)
tr = Tracer(sim, snap.border, snap.out7ffd, snap.outfffd, list(snap.ay), snap.outfe, False)
sim.set_tracer(tr)
regs = sim.registers; pc = snap.pc; t0 = regs[25]
K = lambda a: mem.banks[2][a - 0xE000 + 0xAF00 - 0x8000]
def setK(a, v): mem.banks[2][a - 0xE000 + 0xAF00 - 0x8000] = v
if os.environ.get('SAFE') == '1': mem.banks[0][0x15FC] = 0xC9
poked = False; play0 = None; last = None; go = None
for f in range(int(SECS * 50)):
    kb = keys_for(f)
    st = K(0xE000)
    if st < 4 and f % 50 < 3: kb[7] |= 1
    tr.keyboard = kb
    if st == 4 and not poked: setK(0xE061, STAGE); poked = True; print('poked stage at frame', f)
    if st == 7 and go is None: go = f; print('game over at', f)
    if go is not None and f in (go + 5, go + 30, go + 80):
        scr_png(mem.banks[7 if tr.out7ffd & 8 else 5][:6912], '%s_go%d.png' % (PRE, f - go))
    if (st, K(0xE061)) != last: print('f=%d state %d stage %d' % (f, st, K(0xE061))); last = (st, K(0xE061))
    if st == 5 and play0 is None: play0 = f
    sim.trace(pc, -1, 0, t0 + (f + 1) * FRAME, 1, None, None, None, None, None)
    pc = regs[24]
    if SHOTF and SHOTF[0] <= f <= SHOTF[1] and f % 2 == 0:
        scr_png(mem.banks[7 if tr.out7ffd & 8 else 5][:6912], "%s_f%d.png" % (PRE, f))
ns = int(sys.argv[5], 16) if len(sys.argv) > 5 else None
if ns:
    def rd(a): return mem.banks[2][a - 0x8000] if 0x8000 <= a < 0xC000 else mem.banks[5][a - 0x4000] if a < 0x8000 else None
    for r in range(22): print('%2d' % r, ' '.join('%02X' % rd(ns + r * 32 + c) for c in range(32)))
