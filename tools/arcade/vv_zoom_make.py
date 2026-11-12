"""Makes the ending's Vic Viper zoom (4 November 2026): the ship coming
towards the camera from the exploded Xaerous, in 16 sizes instead of the
patch's 6, every size drawn from one head-on model (vv_model.py: shapes,
drawn 16 times over and reduced), in the colours of the ship the player
flies.

Konami's zoom (0:4BD8, ending step 4) shows six drawings for 64, 40, 16, 12,
8 and 4 ticks (4C10 on; the first from step 3's wait), the last held 32
ticks more (step 5).  Here the ship's size follows a perspective approach
fitted to Konami's (a / (T0 - t): its first size at the start, full size at
tick 140), and it drifts down as Konami's does (its middle from Y 60 to 72,
X 128).  Each size is cut into 16 x 16 sprites (4-bit, palette 15).

  vv_zoom_make.py ../../spec/nx_vvzoom.py"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vv_model as model
N = 16
S0 = 0.17
LEVELS = [S0 * (1 / S0) ** (i / (N - 1)) for i in range(N)]
T_END = 140                              # full size (Konami's last drawing)
T0 = T_END / (1 - S0); A = T0 - T_END    # a / (T0 - t): S0 at 0, 1 at T_END
def size(t): return min(1.0, A / (T0 - t)) if t < T0 else 1.0
TICKS = 144 + 32
TABLE = []
for t in range(TICKS):
    s = size(t)
    TABLE.append(min(range(N), key=lambda i: abs(math.log(LEVELS[i] / s))))
def q9(c):
    r, g, b = (round(v * 7 / 255) for v in c)
    return (r, g, b)
PAL = sorted(set(q9(c) for c in model.C.values()))
assert len(PAL) <= 14
def nib(c):
    q = min(PAL, key=lambda p: sum((a - b * 255 / 7) ** 2 for a, b in zip(c, p)))
    return 2 + PAL.index(q)
def tiles(px):
    left = set(px); out = []
    while left:
        py = min(p[1] for p in left); px0 = min(p[0] for p in left if p[1] == py)
        best = max(range(px0 - 15, px0 + 1), key=lambda x0: (sum(1 for p in left if x0 <= p[0] < x0 + 16 and py <= p[1] < py + 16), -abs(x0 - (px0 - 7))))
        cov = {p for p in left if best <= p[0] < best + 16 and py <= p[1] < py + 16}
        out.append((best, py, cov)); left -= cov
    return out
FRAMES = []
for i, s in enumerate(LEVELS):
    w, h, px = model.render(s)
    yc = 60 + 12 * (s - S0) / (1 - S0)
    ox = math.floor(128 - model.CX * s + 0.5); oy = math.floor(yc - model.CY * s + 0.5)
    spr = []
    for (x0, y0, cov) in tiles(px):
        rows = [''.join('%X' % nib(px[(x0 + x, y0 + y)]) if (x0 + x, y0 + y) in cov else '0' for x in range(16)) for y in range(16)]
        spr.append((ox + x0, oy + y0, rows))
    FRAMES.append(spr)
P15 = [(0, 0)] * 16
for k, (r, g, b) in enumerate(PAL):
    P15[2 + k] = (r << 5 | g << 2 | b >> 1, b & 1)
with open(sys.argv[1], 'w') as f:
    f.write('"""The ending\'s Vic Viper zoom (made by tools/arcade/vv_zoom_make.py):\n'
            'FRAMES, each size\'s sprites (X, Y, 16 rows of 16 pixels, 4-bit);\n'
            'TABLE, the size for each tick of the zoom (Konami\'s steps 4 and 5);\n'
            'PAL15, palette 15 (entries 0-15, Next 9-bit)."""\n')
    f.write('FRAMES = [\n')
    for spr in FRAMES:
        f.write('    [\n%s    ],\n' % ''.join('        (%d, %d, %r),\n' % (x, y, rows) for (x, y, rows) in spr))
    f.write(']\nTABLE = %r\nPAL15 = %r\n' % (TABLE, P15))
print('%d sizes, %d sprites (at most %d a size), %d colours; sizes from tick: %s' % (
    N, sum(len(s) for s in FRAMES), max(len(s) for s in FRAMES), len(PAL),
    [TABLE.index(i) for i in range(N)]))
