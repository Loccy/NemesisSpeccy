import math
import os; HERE = os.path.dirname(os.path.abspath(__file__)); exec(open(os.path.join(HERE, 'final_base.py')).read())
c9 = lambda r, g, b: (r * 255 // 7, g * 255 // 7, b * 255 // 7)
def redify_px(p):
    r, g, b = p[:3]; L = (r + g + b) / 3
    if r > g and b < 0.6 * g and r > 150:                # orange and yellow accents -> blue, as the arcade's red pod
        return c9(5, 7, 7) if L > 170 else c9(2, 4, 7) if L > 90 else c9(0, 1, 4)
    return c9(7, 6, 5) if L > 220 else c9(7, 5, 4) if L > 170 else c9(7, 3, 3) if L > 120 else c9(5, 0, 1) if L > 70 else c9(3, 0, 0) if L > 30 else c9(1, 0, 0)
def redify(g):
    o = Image.new('RGBA', g.size, (0, 0, 0, 0))
    for y in range(g.height):
        for x in range(g.width):
            p = g.getpixel((x, y))
            if p[3]: o.putpixel((x, y), redify_px(p) + (255,))
    return o
# the walkers (three original drawings, coloured, then Konami's flips)
def wmask(n):
    b = sp[n*32:n*32+32]; return [[bool(((b[r] << 8) | b[16 + r]) & (0x8000 >> c)) for c in range(16)] for r in range(16)]
def walker(n, P):
    m = wmask(n)
    out = set(); st = [(r, c) for r in range(16) for c in (0, 15) if not m[r][c]] + [(r, c) for c in range(16) for r in (0, 15) if not m[r][c]]
    out.update(st)
    while st:
        r, c = st.pop()
        for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            q = (r + d[0], c + d[1])
            if 0 <= q[0] < 16 and 0 <= q[1] < 16 and q not in out and not m[q[0]][q[1]]: out.add(q); st.append(q)
    hole = [(r, c) for r in range(16) for c in range(16) if not m[r][c] and (r, c) not in out]
    cy = sum(p[0] for p in hole) / len(hole); cx = sum(p[1] for p in hole) / len(hole)
    rad = sorted(math.hypot(r - cy, c - cx) for r, c in hole)[len(hole) // 4]
    g = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    for r in range(16):
        for c in range(16):
            if not m[r][c]: continue
            d = math.hypot(r - cy, c - cx); dy = r - cy; dx = c - cx
            if d < rad: col = P['hi'] if dx + dy < -1 else P['lo'] if dx + dy > 1 else P['mid']
            elif d < rad + 2.6: col = P['ring_up'] if dy < 0 else P['ring_dn']
            elif dy < -1: col = P['top'] if (r == 0 or not m[r - 1][c]) else P['upper']
            else: col = P['foot'] if ((r == 15 or not m[r + 1][c]) and dy > 2) else P['leg']
            g.putpixel((c, r), col + (255,))
    for r, c in hole:                   # the gaps inside it black, not see-through (8 November 2026)
        g.putpixel((c, r), (0, 0, 0, 255))
    return g
WN = dict(hi=c9(6,6,3), mid=c9(6,3,0), lo=c9(4,2,0), ring_up=c9(6,6,5), ring_dn=c9(4,6,5), top=c9(7,7,7), upper=c9(6,6,6), leg=c9(2,5,5), foot=c9(0,3,3))
WC = dict(hi=c9(5,7,7), mid=c9(2,4,7), lo=c9(0,1,4), ring_up=c9(7,5,4), ring_dn=c9(7,3,3), top=c9(7,6,5), upper=c9(7,4,3), leg=c9(5,0,1), foot=c9(2,0,0))
def orient(g, k):
    if k & 1: g = g.transpose(Image.FLIP_TOP_BOTTOM)
    if k & 2: g = g.transpose(Image.FLIP_LEFT_RIGHT)
    return g
W_ORDER = [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1), (0, 3), (1, 3), (2, 3), (0, 2), (1, 2), (2, 2)]
wn = [walker(n, WN) for n in (52, 53, 54)]; wc = [walker(n, WC) for n in (52, 53, 54)]
walk_new = [orient(wn[i], k) for i, k in W_ORDER]; walk_red = [orient(wc[i], k) for i, k in W_ORDER]
# the rock as built (fire colours): its own pattern in the Next's fire scheme is in the pack; shown as the MSX shape
# turrets
_tur = [(7 + 17 * i, 96, 20 + 17 * i, 109) for i in range(13)]; _pick = [0, 2, 4, 8, 10, 12]
tur_g = [cut('Small Enemies.png', _tur[i]) for i in _pick]; tur_c = [cut('Small Enemies.png', _tur[i], flip=True) for i in _pick]
def frame_col(f, colour):
    g = frame(f); o = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    for y in range(16):
        for x in range(16):
            if g.getpixel((x, y))[3]: o.putpixel((x, y), tms[colour] + (255,))
    return o
groups = [
 # name, [(row label, [images])...]
 ('Fans (type 2, characters)', [('MSX', [frame(f) for f in range(0, 4)]), ('new', fan)]),
 ('Turret, ground (type 1, characters)', [('MSX', [frame(f) for f in range(0x0F, 0x15)]), ('new', tur_g),
                                         ('MSX carrier', [frame_col(f, 8) for f in range(0x0F, 0x15)]), ('new carrier', [redify(g) for g in tur_g])]),
 ('Turret, ceiling (type 1, characters)', [('MSX', [frame(f) for f in range(0x1B, 0x21)]), ('new', tur_c),
                                          ('MSX carrier', [frame_col(f, 8) for f in range(0x1B, 0x21)]), ('new carrier', [redify(g) for g in tur_c])]),
 ('Pod (type 3, p35-39)', [('MSX', [spr(p, 14) for p in range(35, 40)]), ('new', pod),
                           ('MSX carrier', [spr(p, 8) for p in range(35, 40)]), ('new carrier', [redify(g) for g in pod])]),
 ('Tilting jet (type 4, p44-46)', [('MSX', [spr(p, 2) for p in (44, 45, 46)]), ('new', jet),
                                   ('MSX carrier', [spr(p, 8) for p in (44, 45, 46)]), ('new carrier', [redify(g) for g in jet])]),
 ('Walker (type 5, p52-63)', [('MSX', [spr(p, 10) for p in range(52, 64)]), ('new', walk_new),
                              ('MSX carrier', [spr(p, 8) for p in range(52, 64)]), ('new carrier', walk_red)]),
 ('Robot (type 6, p40-43)', [('MSX', [spr(p, 5) for p in range(40, 44)]), ('new', rob),
                             ('MSX carrier', [spr(p, 8) for p in range(40, 44)]), ('new carrier', [redify(g) for g in rob])]),
 ('Hatch saucer (type 7, characters)', [('MSX', [frame(f) for f in range(4, 9)]), ('new', sau)]),
 ('Capsules (types 12h blue, 13h red, characters)', [('MSX', [frame(0x22), frame(0x21)]), ('new', crab)]),
 ('Enemy shot (p34)', [('MSX', [spr(34, 15)]), ('new', [orb])]),
 ('Explosion (type 15h, p30-33)', [('MSX', [spr(p, 15) for p in range(30, 34)]), ('new', expl)]),
]
S = 5; cw = 16 * S + 6; maxn = 12
height = sum(22 + len(rows) * (16 * S + 6) + 8 for _, rows in groups) + 40
img = Image.new('RGB', (230 + maxn * cw, height), (0, 0, 0)); dr = ImageDraw.Draw(img)
dr.text((8, 8), "Stage 1: Konami's original MSX graphics (from nem.rom) and their replacements. Carrier rows: the red versions for enemies that leave a capsule.", fill=(230, 230, 230))
y = 32
for name, rows in groups:
    dr.line([(8, y - 4), (img.width - 8, y - 4)], fill=(60, 60, 70))
    dr.text((8, y), name, fill=(255, 220, 120)); y += 18
    for lab, ims in rows:
        dr.text((24, y + 30), lab, fill=(200, 200, 200) if 'new' in lab else (150, 150, 160))
        for i, g in enumerate(ims):
            b = g.resize((16 * S, 16 * S), Image.NEAREST); img.paste(b, (230 + i * cw, y), b)
        y += 16 * S + 6
    y += 12
img.save('stage1_final_sheet.png'); print(img.size)
