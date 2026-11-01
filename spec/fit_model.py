"""Python model of the runtime colour fit (convert.asm), plus the full search."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, collections
from convert import colour_fit, PALETTES, dist2
from extract import TMS
SH = 8
D = [[[dist2(TMS[m], PALETTES[br][z]) >> SH for z in range(8)] for m in range(16)] for br in (0, 1)]
NEARq = [[min(range(8), key=lambda z: (D[br][m][z], z)) for m in range(16)] for br in (0, 1)]

def heur_q(rows):
    counts = [0] * 16; flags = [0] * 16
    for p, c in rows:
        n = bin(p).count('1'); counts[c >> 4] += n; counts[c & 15] += 8 - n
        if n <= 1: flags[c & 15] += 1
        elif n >= 7 or c >> 4 == c & 15: flags[c >> 4] += 1
        else: flags[c >> 4] |= 0x80; flags[c & 15] |= 0x80
    # colours seen only as one or two solid rows (border lines) do not vote
    if sum(1 for f in flags if f >= 3) >= 2:
        for m in range(16):
            if 1 <= flags[m] <= 2: counts[m] = 0
    present = [m for m in range(16) if counts[m]]
    best = None
    for br in (0, 1):
        cands = []
        for m in present:
            z = NEARq[br][m]
            if z not in cands: cands.append(z)
        for ink in cands:
            for paper in cands:
                err = sum(counts[m] * min(D[br][m][ink], D[br][m][paper]) for m in present)
                key = (err, ink == paper, (ink != 7 and paper != 0), ink | paper << 3 | br << 6)
                if best is None or key < best[0]: best = (key, ink, paper, br)
    _, ink, paper, br = best
    bits = []
    for p, c in rows:
        fgb = ink != paper and D[br][c >> 4][ink] < D[br][c >> 4][paper]
        bgb = ink != paper and D[br][c & 15][ink] < D[br][c & 15][paper]
        bits.append((p if fgb else 0) | ((~p & 255) if bgb else 0))
    return bytes(bits) + bytes([ink | paper << 3 | br << 6])
