"""Run convert_tile from the assembled build on every distinct tile of every
captured stage state; compare with the Python model and measure T-states."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, pickle, re
from skoolkit.simulator import Simulator
from skoolkit.snapshot import Snapshot
sys.path.insert(0, NEM_ROOT + '/spec')
from fit_model import heur_q
syms = {}
for l in open(NEM_ROOT + '/spec/nemesis.sym'):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
snap = Snapshot.get(NEM_ROOT + '/spec/nemesis.sna')
B = snap.memory.banks
mem = bytearray(0x10000)
mem[0x4000:0x8000] = B[5]; mem[0x8000:0xC000] = B[2]; mem[0xC000:] = B[3]               # page B: the colour fit
sim = Simulator(mem)
r = sim.registers
def convert(rows):
    for i, (p, c) in enumerate(rows):
        mem[syms['cv_pat'] + i] = p; mem[syms['cv_col'] + i] = c
    sp = 0xAEA0; mem[sp] = 0xFE; mem[sp + 1] = 0xFF; mem[0xFFFE] = 0x18; mem[0xFFFF] = 0xFE
    r[12] = sp; r[24] = syms['convert_tile']; t0 = r[25]
    while r[24] != 0xFFFE:
        sim.opcodes[mem[r[24]]]()
    return bytes(mem[syms['cv_out']:syms['cv_out'] + 9]), r[25] - t0
if __name__ == '__main__':
    S = pickle.load(open(NEM_ROOT + '/spec/vram_states.pkl', 'rb'))
    seen = set(); bad = 0; n = 0; T = []
    for k, vr in S.items():
        for th in range(3):
            for ch in range(256):
                o = th * 0x800 + ch * 8
                rows = tuple((vr[0x2000 + o + l], vr[o + l]) for l in range(8))
                if rows in seen: continue
                seen.add(rows)
                out, t = convert(rows); T.append(t); n += 1
                want = heur_q(rows)
                if out != want:
                    bad += 1
                    if bad <= 5: print('mismatch', k, th, ch, out.hex(), want.hex())
    T.sort()
    print('tiles', n, 'mismatches', bad, 'T min %d median %d mean %d max %d' % (T[0], T[len(T) // 2], sum(T) // len(T), T[-1]))
