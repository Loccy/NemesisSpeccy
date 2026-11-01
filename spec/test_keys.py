"""Run kb_compute from the build on random keyboard states; compare kb_cache
with the key maps in tables.py."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re, random
from skoolkit.simulator import Simulator
from skoolkit.snapshot import Snapshot
sys.path.insert(0, NEM_ROOT + '/spec')
import tables as T
syms = {}
for l in open(NEM_ROOT + '/spec/nemesis.sym'):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
snap = Snapshot.get(NEM_ROOT + '/spec/nemesis.sna'); B = snap.memory.banks
mem = bytearray(0x10000); mem[0x4000:0x8000] = B[5]; mem[0x8000:0xC000] = B[2]; mem[0xC000:] = B[0]
sim = Simulator(mem); r = sim.registers
bad = 0
for trial in range(3000):
    rows = [0x1F ^ (random.getrandbits(5) if random.random() < 0.3 else 0) for _ in range(8)]
    for i, v in enumerate(rows): mem[syms['kb_rows'] + i] = v | 0xE0
    r[12] = 0xBF00; mem[0xBF00] = 0; mem[0xBF01] = 0   # return to 0
    r[24] = syms['kb_compute']
    while r[24] != 0: sim.run()
    pressed = lambda k: not rows[T.KEY[k][0]] >> T.KEY[k][1] & 1
    exp = [0xFF ^ sum(1 << b for b, k in enumerate(row) if k and pressed(k)) for row in T.MSX_MATRIX]
    exp.append(0x3F ^ sum(1 << b for b, ks in enumerate(T.JOY) if any(pressed(k) for k in ks)))
    got = list(mem[syms['kb_cache']:syms['kb_cache'] + 10])
    if got != exp:
        bad += 1
        if bad < 4: print(rows, got, exp)
print('trials 3000 mismatches', bad)
