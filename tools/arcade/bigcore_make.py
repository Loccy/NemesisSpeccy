"""Makes the Big Core in the arcade's drawing (4 November 2026), from the
arcade's bosses sheet (Bosses.png: the body, its five cores, the strip of
four wall bars and a ball), in the place of Konami's 11 x 8 characters.

* The body: the sheet's, columns 11-98 (Konami's 88: 4 pixels off the jaw
  tips, 2 off the tail; where a row is cut its last two pixels are shaded
  darker), rows 36-99 (Konami's 64, the core level with Konami's).
* The core: one of the sheet's five (19 pixels apart from 9, 105), at X 36,
  Y 24 of the 88 x 64: grey when it comes, bluer every two hits (Konami's
  life, E789, from 16h down), none once it has gone (face 2 in E786, or
  dead: E155).  Konami's core cells (its "mouth", X 32-55) are where the
  hits count.
* The walls: the sheet's strip (61-81, 22-29: four bars, then a ball) in
  the mouth, level with the core, the ball 10 pixels in front of it.  Konami's
  walls are its life over 4 (1:7E91): 5 four bars and the ball, then a bar
  fewer each 4 hits from the front, 1 the ball alone, 0 none.
* The port shows the Big Core as 24 16 x 16 sprites, 6 x 4 over its 11 x 8
  characters (nx_l2.asm lo_bpats), in palette 15: the wall drawings fall in
  blocks 6, 7, 12 and 13; the other 20 never change (the core's channel left
  empty in them).  The core is a sprite of its own (nx_tur.asm), in palette
  14 (its blues and greys).  The sheet's colours to the Next's 9 bits, at most
  14 a palette (the rarest to the nearest kept).

  ARCADE_DIR=... bigcore_make.py ../../spec/nx_bigcore.py"""
import os, sys
from PIL import Image
D = os.environ.get('ARCADE_DIR', '.').rstrip('/') + '/'
sh = Image.open(D + 'Bosses.png').convert('RGB'); sp = sh.load()
M = (255, 0, 255)
X0, Y0 = 11, 36                 # the sheet's pixel at Konami's 0, 0
CORE_X, CORE_Y = 36, 24
WALL_X, WALL_Y = CORE_X - 31, 28
WALLB = [6, 7, 12, 13]
def q9(c): return tuple(round(v * 7 / 255) for v in c)
def body():
    px = {}
    for y in range(64):
        for x in range(88):
            c = sp[X0 + x, Y0 + y]
            if c != M and not (X0 + x > 100 and c[0] < 140): px[(x, y)] = q9(c)
    # rows cut at either end: their last two pixels darker
    for y in range(64):
        for side, rng in (('r', range(X0 + 88, 112)), ('l', range(0, X0))):
            if not any(sp[x, Y0 + y] != M for x in rng): continue
            xs = sorted(x for (x, yy) in px if yy == y)
            if not xs: continue
            e = xs[-1] if side == 'r' else xs[0]; d = -1 if side == 'r' else 1
            for k, f in ((0, 0.45), (1, 0.72)):
                p = (e + d * k, y)
                if p in px: px[p] = tuple(int(v * f + 0.5) for v in px[p])
    # the channel where the core goes, and the mouth where the walls go, as
    # the sheet has them (empty there): nothing to take out
    return px
def walls(px, v):
    bars = max(0, v - 1); ball = v >= 1
    for y in range(8):
        for x in range(21):
            c = sp[61 + x, 22 + y]
            if c == M: continue
            if x < 16 and (x // 4) < 4 - bars: continue
            if x >= 16 and not ball: continue
            px[(WALL_X + x, WALL_Y + y)] = q9(c)
def core(f):
    return [[q9(sp[9 + 19 * f + x, 105 + y]) if sp[9 + 19 * f + x, 105 + y] != M else None for x in range(16)] for y in range(16)]
def block(px, b):
    bx, by = b % 6 * 16, b // 6 * 16
    return [[px.get((bx + x, by + y)) for x in range(16)] for y in range(16)]
base = body()
TILES = []                      # (block, rows of 9-bit colours or None)
for b in range(24):
    if b not in WALLB: TILES.append((b, 'static', 0, block(base, b)))
for v in range(6):
    p = dict(base); walls(p, v)
    for b in WALLB: TILES.append((b, 'wall', v, block(p, b)))
CORES = [(-1, 'core', f, core(f)) for f in range(5)]
assert len(TILES) == 44
def palette(tiles):
    from collections import Counter
    cnt = Counter(c for t in tiles for row in t[3] for c in row if c is not None)
    cols = [c for c, _ in cnt.most_common()]
    keep = cols[:14]
    def near(c): return min(keep, key=lambda k: sum((a - b) ** 2 for a, b in zip(c, k)))
    return keep, {c: near(c) for c in cols}, len(cols)
P15, M15, n15 = palette(TILES)
P14, M14, n14 = palette(CORES)
def nib(t):
    keep, mp = (P14, M14) if t[0] < 0 else (P15, M15)
    return [''.join('0' if c is None else '%X' % (2 + keep.index(mp[c])) for c in row) for row in t[3]]
def enc(c):
    r, g, b = c
    return (r << 5 | g << 2 | b >> 1, b & 1)
# Konami's own blocks with nothing in them are never shown (lo_bossspr): none of ours may have anything there
rom = open(os.environ.get('NEM_ROM', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'nem.rom')), 'rb').read()
bodyc = [rom[0x2000 + 0x7EE6 - 0x6000 + i] for i in range(88)]
for k in range(6):
    bodyc[(3 + k // 3) * 11 + 1 + k % 3] = 1; bodyc[(3 + k // 3) * 11 + 4 + k % 3] = 1
def kempty(b):
    r, c = b // 6 * 2, b % 6 * 2
    return not any(bodyc[(r + i) * 11 + c + j] for i in range(2) for j in range(2) if c + j < 11)
lost = [b for b in range(24) if kempty(b) and any(c for row in block(base, b) for c in row)]
with open(sys.argv[1], 'w') as f:
    f.write('"""The Big Core in the arcade\'s drawing (made by tools/arcade/bigcore_make.py):\n'
            'TILES, 44 16 x 16 drawings (4-bit, palette 15): the 20 blocks that never\n'
            'change, then the wall blocks (6, 7, 12, 13) for walls 0-5; BLOCK, each\n'
            'tile\'s block; CORES, the five cores (palette 14); PAL14, PAL15 (entries\n'
            '0-15, Next 9-bit)."""\n')
    f.write('TILES = [\n%s]\n' % ''.join('    %r,\n' % (nib(t),) for t in TILES))
    f.write('BLOCK = %r\n' % ([t[0] for t in TILES],))
    f.write('CORES = [\n%s]\n' % ''.join('    %r,\n' % (nib(t),) for t in CORES))
    for name, keep in (('PAL14', P14), ('PAL15', P15)):
        pal = [(0, 0)] * 16
        for i, c in enumerate(keep): pal[2 + i] = enc(c)
        f.write('%s = %r\n' % (name, pal))
print('palette 15: %d colours (%d on the sheet), 14: %d (%d); blocks Konami leaves empty with ours in them: %s'
      % (len(P15), n15, len(P14), n14, lost))
