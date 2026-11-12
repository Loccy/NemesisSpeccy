"""Makes stage 8's brain in the arcade's style (4 November 2026): the arcade
brain ("Xaerous Brain" on the arcade's bosses sheet, Bosses.png) and its
electricity, after the arcade.

* The brain: Konami draws it with characters, 8 x 8 of them (rows 7-14,
  columns 12-19 of the screen where the scroll stops, distance 19Fh).  The
  arcade brain (60 x 53) is put in that block at full size (a pixel right
  and three down from its middle, where none of it falls outside Konami's
  characters) and the brain's characters take its pixels, in the stage's scenery palette
  (D1-DF).  Konami's tendrils (characters A1-BF on that screen) are left
  black: the electricity is drawn with sprites instead.  On that screen each
  of these characters is used once in its third, and nowhere else in the
  stage (a run through all 382 screens of stage 8).
* The sockets: Konami's type 11h objects (2:88D3, six, the boss script at
  2:88F8), one character each, written into the screen (frames 33h-36h of
  5:91D1): AB and B0 at the top (the top third), A6 and AB at the bottom
  (the bottom third, upside down).  They take the arcade's socket.
* The electricity: the arcade's lines (cyan and green, white where they
  cross), squashed between the brain and the sockets (the brain at full
  size; the line ends on Konami's sockets), each pixel given to the bolt
  whose socket lies nearest its direction from the brain's middle, and each
  bolt cut into 16 x 16 sprites (4-bit: 2 cyan, 3 green, 4 white; nx_tur.asm
  swaps cyan and green with the palette, 14 or 15).

  ARCADE_DIR=... st8_brain_make.py st8_brain.py ../../../spec/nx_st8.py
  (then put_blocks.py 8 st8_brain.py)"""
import os, sys, math
from PIL import Image
D = os.environ.get('ARCADE_DIR', '.').rstrip('/') + '/'
sh = Image.open(D + 'Bosses.png').convert('RGB'); sp = sh.load()
# Konami's screen at the brain (rows 3-18 of the map, distance 19Fh)
SCREEN = bytes.fromhex(
    '0000000000000000000000000000000000000000000000000000000000000000'
    '00000000000000000000acad000000a300000000b2b1000000b6000000000000'
    '0000000000000000000000aeaf0000a8a90000b4b30000000000000000000000'
    '0000000000000000000000babb0000a5a40000bebd00000000b6000000000000'
    '000000000000000000000000bc01000a0b0005bf000000000000000000000000'
    'b600000000000000000000000002030c0d070800b500b5000000000000000000'
    '00000000000000000000000000041a1b1c1d0900000000000000000000000000'
    '000000000000000000000000361f202122232437000000000000000000000000'
    'b60000000000000000000000322728292a2b2c33b500b5000000000000000000'
    '0000000000000000b500b5003431301e2e2d2f350000000000b6000000000000'
    '0000000000000000000000000011121825261300000000000000000000000000'
    '00000000000000000000000000141516170e10000000000000b6000000000000'
    '000000000000000000b500b5a6a700a4a500aaa9000000000000000000000000'
    '000000000000000000000000a9aa00a4a300afae000000000000000000000000'
    '0000000000000000000000a7a80000a2a10000adac0000000000000000000000'
    '0000000000000000000000000000000000000000000000000000000000000000')
assert len(SCREEN) == 16 * 32
def ch(r, c): return SCREEN[(r - 3) * 32 + c]
M = (255, 0, 255)
LINE = {(0, 255, 255): 2, (0, 255, 0): 3, (255, 255, 255): 4}
brain, line = {}, {}
for x in range(228, 362):
    for y in range(150, 305):
        c = sp[x, y]
        if c == M: continue
        if c in LINE: line[(x, y)] = LINE[c]
        else: brain[(x, y)] = c
bx0 = min(p[0] for p in brain); bx1 = max(p[0] for p in brain)
by0 = min(p[1] for p in brain); by1 = max(p[1] for p in brain)
acx, acy = (bx0 + bx1) / 2, (by0 + by1) / 2
TOP, BOT = 153, 296                     # the arcade lines' ends
AT = [232.5, 289.5, 352.5]              # and their X
ocx, ocy = 128.5, 90.5                  # the brain's middle: Konami's block's, 1 right and
                                        # 3 down, where the whole brain falls in its cells
obt, obb = ocy - (acy - by0), ocy + (by1 - acy)
TIP_T, TIP_B = 32, 143                  # just below the top sockets, above the bottom ones
ST = [83.5, 123.5, 171.5]               # the sockets' middles: top (columns 10, 15, 21)
SB = [91.5, 123.5, 163.5]               # and bottom (11, 15, 20)
def xmap(x, t, s):
    x1 = ocx + (x - acx)
    if x <= AT[1]: f = (x - AT[0]) / (AT[1] - AT[0]); xt = s[0] + f * (s[1] - s[0])
    else: f = (x - AT[1]) / (AT[2] - AT[1]); xt = s[1] + f * (s[2] - s[1])
    return x1 + (xt - x1) * t
def place(x, y):
    if y < by0:
        t = (by0 - y) / (by0 - TOP); yy = obt - t * (obt - TIP_T); xx = xmap(x, t, ST)
    elif y > by1:
        t = (y - by1) / (BOT - by1); yy = obb + t * (TIP_B - obb); xx = xmap(x, t, SB)
    else:
        yy = ocy + (y - acy); xx = ocx + (x - acx)
    return math.floor(xx + 0.5), math.floor(yy + 0.5)
def q9(c):
    r, g, b = (round(v * 7 / 255) for v in c)
    return (r << 5 | g << 2 | b >> 1, b & 1)
# the brain's characters and the sockets, in scenery colours D1 on
pal = {}
def sc(c):
    k = q9(c)
    if k not in pal:
        pal[k] = 0xD1 + len(pal); assert pal[k] <= 0xDF, 'too many colours'
    return pal[k]
pix = {}
for (x, y), c in brain.items():
    pix[place(x, y)] = sc(c)
BLOCKS = {}
for r in range(3, 19):
    for c in range(32):
        k = ch(r, c)
        if k in (0, 0xB5, 0xB6): continue
        b = bytes(pix.get((c * 8 + i % 8, r * 8 + i // 8), 0) for i in range(64))
        t = r // 8
        assert (t, k) not in BLOCKS
        BLOCKS[(t, k)] = b
for (x, y) in pix:
    assert ch(y // 8, x // 8) not in (0, 0xB5, 0xB6), ('brain outside its cells', x, y)
sock = {}
for y in range(194, 202):
    for x in range(371, 379):
        c = sp[x, y]
        if c not in (M, (255, 255, 255)): sock[(x - 371, y - 194)] = sc(c)
top = bytes(sock.get((i % 8, i // 8), 0) for i in range(64))
bot = bytes(sock.get((i % 8, 7 - i // 8), 0) for i in range(64))
BLOCKS[(0, 0xAB)] = top; BLOCKS[(0, 0xB0)] = top
BLOCKS[(2, 0xA6)] = bot; BLOCKS[(2, 0xAB)] = bot
# the electricity
el = {}
for (x, y), v in line.items():
    p = place(x, y)
    el[p] = 4 if v == 4 or el.get(p) == 4 else max(el.get(p, 0), v)
tips = [(s, TIP_T) for s in ST] + [(s, TIP_B) for s in SB]
def bolt(p):
    a = math.atan2(p[1] - ocy, p[0] - ocx)
    return min(range(6), key=lambda i: abs((math.atan2(tips[i][1] - ocy, tips[i][0] - ocx) - a + math.pi) % (2 * math.pi) - math.pi))
groups = [{} for _ in range(6)]
for p, v in el.items(): groups[bolt(p)][p] = v
PATS, SPR = [], []
for i, g in enumerate(groups):
    left = set(g)
    while left:
        py = min(p[1] for p in left); px = min(p[0] for p in left if p[1] == py)
        best = max(range(px - 15, px + 1), key=lambda x0: (sum(1 for p in left if x0 <= p[0] < x0 + 16 and py <= p[1] < py + 16), -abs(x0 - (px - 7))))
        cov = {p for p in left if best <= p[0] < best + 16 and py <= p[1] < py + 16}
        rows = []
        for yy in range(16):
            rows.append(''.join('%X' % g.get((best + xx, py + yy), 0) if (best + xx, py + yy) in cov else '0' for xx in range(16)))
        SPR.append((i, best, py, len(PATS))); PATS.append(rows); left -= cov
assert len(PATS) <= 34, len(PATS)
CYAN, GREEN, WHITE = q9((0, 255, 255)), q9((0, 255, 0)), q9((255, 255, 255))
P14 = [(0, 0)] * 16; P15 = [(0, 0)] * 16
P14[2], P14[3], P14[4] = CYAN, GREEN, WHITE
P15[2], P15[3], P15[4] = GREEN, CYAN, WHITE
# the sockets' objects where the scroll stops (Konami's X, Y): top, then bottom
SOCKETS = [(0x50, 0x10), (0x78, 0x10), (0xA8, 0x10), (0x58, 0x90), (0x78, 0x90), (0x98, 0x90)]
with open(sys.argv[1], 'w') as f:
    f.write('"""Stage 8\'s brain and sockets in the arcade\'s style (made by\n'
            'tools/pool/art/st8_brain_make.py, whose docstring says how)."""\nBLOCKS = {\n')
    for k in sorted(BLOCKS): f.write('    (%d, 0x%02X): bytes.fromhex(%r),\n' % (k[0], k[1], BLOCKS[k].hex()))
    f.write('}\nPALETTE = {%s}\n' % ', '.join('0x%02X: %r' % (v, k) for k, v in sorted(pal.items(), key=lambda kv: kv[1])))
with open(sys.argv[2], 'w') as f:
    f.write('"""Stage 8\'s electricity (made by tools/pool/art/st8_brain_make.py):\n'
            'its sprite drawings (16 rows of 16 pixels, 4-bit), each sprite (bolt\n'
            '0-5, X, Y where the scroll stops, drawing), the sockets\' objects (X, Y),\n'
            'and palettes 14 and 15 (entries 0-15, Next 9-bit)."""\n')
    f.write('PATS = [\n%s]\n' % ''.join('    %r,\n' % (r,) for r in PATS))
    f.write('SPR = %r\n' % (SPR,))
    f.write('SOCKETS = %r\n' % (SOCKETS,))
    f.write('PAL14 = %r\nPAL15 = %r\n' % (P14, P15))
print('brain %dx%d, %d characters, %d scenery colours; %d sprites (bolts %s)' % (
    bx1 - bx0 + 1, by1 - by0 + 1, len(BLOCKS), len(pal), len(PATS), [sum(1 for s in SPR if s[0] == i) for i in range(6)]))
