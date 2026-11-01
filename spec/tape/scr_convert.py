"""MSX illustration -> Spectrum SCR.  Per 8x8 cell, the best ink/paper/bright
(each pixel to the nearer, or, in the ships, a 50% checker of the two when
that is nearer still); some cells with their colours restricted or forced."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..'))  # the tree's root
import sys
from PIL import Image
S = NEM_ROOT + '/spec/tape/'
im = Image.open(S + 'illustration_msx.png').convert('RGB'); px = im.load()
N = [(0,0,0),(0,0,0xD7),(0xD7,0,0),(0xD7,0,0xD7),(0,0xD7,0),(0,0xD7,0xD7),(0xD7,0xD7,0),(0xD7,0xD7,0xD7)]
B = [(0,0,0),(0,0,0xFF),(0xFF,0,0),(0xFF,0,0xFF),(0,0xFF,0),(0,0xFF,0xFF),(0xFF,0xFF,0),(0xFF,0xFF,0xFF)]
K, BL, R, M, G, C, Y, W = range(8)
def d(a, b):
    r = (a[0]+b[0])/2
    dr, dg, db = a[0]-b[0], a[1]-b[1], a[2]-b[2]
    return (2+r/256)*dr*dr + 4*dg*dg + (2+(255-r)/256)*db*db
def ships(cx, cy):
    if 7 <= cy <= 12 and 2 <= cx <= 29: return True       # the fortress's body
    if 3 <= cy <= 6 and 12 <= cx <= 19: return True       # its spire
    if 4 <= cy <= 5 and 21 <= cx <= 26: return True       # the small ship
    if 12 <= cy <= 15 and 14 <= cx <= 28: return True     # the column and the Vic Viper's right wing
    if 16 <= cy <= 23 and 8 <= cx <= 23: return True      # the Vic Viper's body, left wing and thrusters
    return False
FORCE = {}      # (cx, cy) -> (bright, ink, paper): every non-black pixel ink
ALLOW = {}      # (cx, cy) -> colours a cell may use
def fit(cx, cy):
    cell = [px[cx*8+x, cy*8+y] for y in range(8) for x in range(8)]
    if (cx, cy) in FORCE:
        br, ink, pap = FORCE[(cx, cy)]
        return br, ink, pap, [[1 if c != (0, 0, 0) else 0 for c in cell[y*8:y*8+8]] for y in range(8)]
    dither = DITHER if ships(cx, cy) else None
    allow = ALLOW.get((cx, cy), range(8))
    cols = {}
    for c in cell: cols[c] = cols.get(c, 0) + 1
    best = None
    for br, P in ((0, N), (1, B)):
        for i in allow:
            for p in allow:
                if p > i: continue
                m = tuple((P[i][k] + P[p][k]) // 2 for k in range(3))
                e = 0
                for c, n in cols.items():
                    o = min(d(c, P[i]), d(c, P[p]))
                    if dither: o = min(o, dither * d(c, m))
                    e += n * o
                if best is None or e < best[0]: best = (e, br, i, p)
    e, br, ink, pap = best
    P = B if br else N
    m = tuple((P[ink][k] + P[pap][k]) // 2 for k in range(3))
    rows = []
    for y in range(8):
        row = []
        for x in range(8):
            c = cell[y*8+x]; di, dp = d(c, P[ink]), d(c, P[pap])
            if dither and dither * d(c, m) < min(di, dp): row.append((x + y) & 1)
            else: row.append(1 if di < dp else 0)
        rows.append(row)
    return br, ink, pap, rows
DITHER = 1.3
def build(path_scr, path_png):
    scr = bytearray(6912); out = Image.new('RGB', (256, 192)); op = out.load()
    for cy in range(24):
        for cx in range(32):
            br, ink, pap, rows = fit(cx, cy); P = B if br else N
            for y in range(8):
                Y = cy*8 + y; v = 0
                for x in range(8):
                    v = v << 1 | rows[y][x]; op[cx*8+x, Y] = P[ink] if rows[y][x] else P[pap]
                scr[((Y & 0xC0) << 5) | ((Y & 7) << 8) | ((Y & 0x38) << 2) | cx] = v
            scr[6144 + cy*32 + cx] = br << 6 | pap << 3 | ink
    open(path_scr, 'wb').write(scr); out.resize((768, 576), Image.NEAREST).save(path_png)
    return scr
if __name__ == '__main__':
    build(S + 'v2.scr', S + 'v2.png')
