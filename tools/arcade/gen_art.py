"""Makes spec/nx_art.py (the Next's arcade-style sprites, as data) from the
arcade sprite sheets (Gradius-Arcade-Assets.zip, unpacked: set ARCADE_DIR)
and nem.rom.  Run once when the art changes; the build itself needs only
spec/nx_art.py.  The cutting, colouring and red versions are as agreed on
3 November 2026 (stage1_final_sheet.png)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'final.py')).read().split("groups = [")[0]
exec(src)
def nine(rgb):
    r, g, b = (round(v * 7 / 255) for v in rgb)
    return r, g, b
def enc(rgb):
    r, g, b = nine(rgb); return ((r << 5) | (g << 2) | (b >> 1), b & 1)
def family(ims):
    cols = set()
    for g in ims:
        for y in range(16):
            for x in range(16):
                p = g.getpixel((x, y))
                if p[3]: cols.add(p[:3])
    cols = sorted(cols, key=lambda c: (sum(c), c))
    assert len(cols) <= 14, len(cols)     # pixels 2-15 (1 is a Konami colour's)
    return {c: i + 2 for i, c in enumerate(cols)}
def rows(g, idx):
    out = []
    for y in range(16):
        out.append(''.join('%X' % (idx[g.getpixel((x, y))[:3]] if g.getpixel((x, y))[3] else 0) for x in range(16)))
    return out
A = family(fan + pod + jet + sau); B = family(tur_g + tur_c + rob); C = family([orb] + expl)
# stage 2's materialising enemy (Konami's type 8, patterns 47-50): the arcade's
# growing ring, its frames 2-5 (the first, a faint dotted ring, has no MSX frame)
mat = [cut('Small Enemies.png', b) for b in ((297, 43, 310, 56), (314, 43, 327, 56), (331, 42, 346, 57), (350, 42, 365, 57))]
E = family(mat)
def blueify_px(p):
    # stage 2's turrets: the teal and white to a blue ramp, the orange kept
    r, g, b = p[:3]; L = (r + g + b) / 3
    if r > g and b < 0.6 * g and r > 150:
        return (r, g, b)
    for t, c in ((220, (7, 7, 7)), (170, (5, 6, 7)), (120, (3, 4, 7)), (70, (2, 2, 6)), (30, (1, 1, 4))):
        if L > t: return tuple(v * 255 // 7 for v in c)
    return tuple(v * 255 // 7 for v in (0, 0, 2))
DB = family([crab[0]]); DR = family([crab[1]])
pal = {}
def palette(idx, f=lambda c: c):
    p = [(0, 0)] * 16
    for c, i in idx.items(): p[i] = enc(f(c))
    return p
WKEYS = ['hi', 'mid', 'lo', 'ring_up', 'ring_dn', 'top', 'upper', 'leg', 'foot']
W = {WN[k]: 2 + i for i, k in enumerate(WKEYS)}
W[(0, 0, 0)] = 11                     # the gaps inside a walker: entry 11, black in palettes 2 and 3
pal[2] = [(0, 0)] * 2 + [enc(WN[k]) for k in WKEYS] + [(0, 0)] * 5
pal[3] = [(0, 0)] * 2 + [enc(WC[k]) for k in WKEYS] + [(0, 0)] * 5
pal[4] = palette(A); pal[5] = palette(A, redify_px)
pal[6] = palette(B); pal[7] = palette(B, redify_px)
pal[8] = palette(C); pal[9] = palette(DB); pal[10] = palette(DR)
pal[11] = palette(B, blueify_px); pal[12] = palette(E)
sprites = {}
for i, g in enumerate(expl): sprites[30 + i] = (0x80, rows(g, C))
sprites[34] = (0x80, rows(orb, C))
for i, g in enumerate(pod): sprites[35 + i] = (0x41, rows(g, A))
for i, g in enumerate(rob): sprites[40 + i] = (0x61, rows(g, B))
for i, g in enumerate(jet): sprites[44 + i] = (0x41, rows(g, A))
for i, g in enumerate(mat): sprites[47 + i] = (0xC0, rows(g, E))
walkers = {52 + j: (0x21, rows(walk_new[j], W)) for j in range(12)}
# drawings of Konami's patterns as a later stage loads them (stage, pattern):
# stage 3's spinning disc (47-50), the arcade's frame for frame, and its spoked
# wheel (55-58), which the arcade has no match for: Konami's own shapes in
# palette 4, lit from the top left so the light stays put as the spokes turn
import math
disc = [cut('Small Enemies.png', b) for b in ((61, 21, 72, 36), (76, 21, 85, 36), (89, 21, 97, 36), (101, 21, 106, 36))]
staged = {}
for i, g in enumerate(disc): staged[(3, 47 + i)] = (0x41, rows(g, A))
from orig_sprites import sprites as konami_sprites
_sp3 = konami_sprites(3)
def wheel(k):
    b = _sp3[k * 32:k * 32 + 32]
    pts = [(c, r) for r in range(16) for c in range(16) if ((b[r] << 8) | b[16 + r]) & (0x8000 >> c)]
    cx = (min(c for c, r in pts) + max(c for c, r in pts)) / 2; cy = (min(r for c, r in pts) + max(r for c, r in pts)) / 2
    R = max(math.hypot(c - cx, r - cy) for c, r in pts)
    g = [[0] * 16 for _ in range(16)]
    for c, r in pts:
        dx, dy = c - cx, r - cy; d = math.hypot(dx, dy)
        lit = -(dx + dy) / (d * 1.414) if d else 1.0
        if d >= R - 1.6:                                       # the rim
            v = 11 if lit > 0.55 else 10 if lit > 0.1 else 8 if lit > -0.35 else 7 if lit > -0.75 else 5
        elif d <= 2.6:                                         # the hub
            v = 9 if lit > 0.3 and d > 0.6 else 6 if lit > -0.4 or d < 0.6 else 4
        else:                                                  # the spokes
            v = 13 if lit > 0.5 else 12 if lit > -0.1 else 10 if lit > -0.6 else 8
        g[r][c] = v
    return [''.join('%X' % v for v in row) for row in g]
for k in range(55, 59): staged[(3, k)] = (0x41, wheel(k))
# stage 5's own enemies, which the arcade has no match for (4 November 2026):
# Konami's shapes shaded, lit from the top left, their inner details (holes
# in the MSX pattern) as darker shading.  The crescents (40-43) in salmon and
# orange with a red twin, the balls (52-59: clusters of three and the single
# balls they break into) in pink, their inner ring of dots (light shading)
# a band one step darker, the bone claws (60-63) in gold, the stars (51) in
# ice blue.  Palette 14: the crescents' ramp (2-6), gold (7-10), ice
# (11-14); palette 15: the red twin's ramp at the crescents' entries (2-6),
# pink (7-11).
_sp5 = konami_sprites(5)
def _bits5(k):
    return [[((_sp5[k * 32 + r] << 8) | _sp5[k * 32 + 16 + r]) >> (15 - c) & 1 for c in range(16)] for r in range(16)]
def _outside(m):
    out = [[False] * 16 for _ in range(16)]
    st = [(y, x) for y in range(16) for x in range(16) if (y in (0, 15) or x in (0, 15)) and not m[y][x]]
    for y, x in st: out[y][x] = True
    while st:
        y, x = st.pop()
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < 16 and 0 <= nx < 16 and not m[ny][nx] and not out[ny][nx]:
                out[ny][nx] = True; st.append((ny, nx))
    return out
def _ring(m):
    """the balls' inner ring of dots, as pixels: single holes (bone on 3 or 4
    sides) 3.5-6.5 from the disc's centre, not touching another such hole,
    near the typical radius, and the gaps between neighbouring dots"""
    out = _outside(m)
    ys = [y for y in range(16) for x in range(16) if m[y][x]]; xs = [x for y in range(16) for x in range(16) if m[y][x]]
    cy, cx = (min(ys) + max(ys)) / 2, (min(xs) + max(xs)) / 2
    for _ in range(3):              # the centre: the central hole ring's centroid
        hs = [(y, x) for y in range(16) for x in range(16) if not m[y][x] and not out[y][x] and math.hypot(y - cy, x - cx) < 3.2]
        if hs: cy, cx = sum(h[0] for h in hs) / len(hs), sum(h[1] for h in hs) / len(hs)
    d = []
    for y in range(16):
        for x in range(16):
            if m[y][x] or out[y][x]: continue
            n = sum(1 for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)) if 0 <= ny < 16 and 0 <= nx < 16 and m[ny][nx])
            if n >= 3 and 3.5 <= math.hypot(y - cy, x - cx) <= 6.5: d.append((y, x))
    d = [(y, x) for y, x in d if not any((y + a, x + b) in d for a in (-1, 0, 1) for b in (-1, 0, 1) if a or b)]
    if len(d) < 5: return set()
    rs = sorted(math.hypot(y - cy, x - cx) for y, x in d); med = rs[len(rs) // 2]
    d = [(y, x) for y, x in d if abs(math.hypot(y - cy, x - cx) - med) <= 0.9]
    d.sort(key=lambda p: math.atan2(p[0] - cy, p[1] - cx))
    px = set(d)
    for i in range(len(d)):
        (y0, x0), (y1, x1) = d[i], d[(i + 1) % len(d)]
        n = max(abs(y1 - y0), abs(x1 - x0))
        if n > 3: continue
        for k in range(1, n):
            y = int(round(y0 + (y1 - y0) * k / n)); x = int(round(x0 + (x1 - x0) * k / n))
            if m[y][x]: px.add((y, x))
    return px
def _shade5(k, first, steps, ring=False):
    """rows of entry numbers (first .. first + steps - 1, dark to light)"""
    m = _bits5(k)
    rp = _ring(m) if ring else set()
    for y, x in rp: m[y][x] = 1
    out = _outside(m)
    ins = lambda y, x: 0 <= y < 16 and 0 <= x < 16 and not out[y][x]
    pts = [(y, x) for y in range(16) for x in range(16) if ins(y, x)]
    y0, y1 = min(p[0] for p in pts), max(p[0] for p in pts); x0, x1 = min(p[1] for p in pts), max(p[1] for p in pts)
    g = [[0] * 16 for _ in range(16)]
    for y, x in pts:
        t = 0.62 if m[y][x] else 0.22
        t += 0.22 * ((not ins(y - 1, x)) + (not ins(y, x - 1))) / 2
        t -= 0.2 * ((not ins(y + 1, x)) + (not ins(y, x + 1))) / 2
        t += 0.18 * (0.5 - ((y - y0) / max(1, y1 - y0) + (x - x0) / max(1, x1 - x0)) / 2)
        l = max(0, min(steps - 1, int(t * steps)))
        if (y, x) in rp: l = max(0, l - 1)
        g[y][x] = first + l
    return [''.join('%X' % v for v in row) for row in g]
def _enc7(r, g, b): return ((r << 5) | (g << 2) | (b >> 1), b & 1)
FIRE = [(3, 1, 0), (5, 2, 1), (7, 4, 2), (7, 5, 3), (7, 7, 5)]
RED = [(2, 0, 0), (4, 1, 1), (6, 2, 1), (7, 4, 3), (7, 6, 5)]
GOLD = [(3, 2, 0), (5, 4, 0), (7, 6, 1), (7, 7, 5)]
ICE = [(1, 2, 5), (3, 4, 7), (5, 6, 7), (7, 7, 7)]
PINK = [(2, 0, 1), (4, 1, 2), (6, 3, 4), (7, 5, 5), (7, 7, 7)]
pal[14] = [(0, 0)] * 2 + [_enc7(*c) for c in FIRE + GOLD + ICE] + [(0, 0)]
pal[15] = [(0, 0)] * 2 + [_enc7(*c) for c in RED + PINK] + [(0, 0)] * 4
for k in range(40, 44): staged[(5, k)] = (0xE1, _shade5(k, 2, 5))
staged[(5, 51)] = (0xE0, _shade5(51, 11, 4))
for k in range(52, 60): staged[(5, k)] = (0xF0, _shade5(k, 7, 5, ring=True))
for k in range(60, 64): staged[(5, k)] = (0xE0, _shade5(k, 7, 4))
# stage 6's brains (4 November 2026): the arcade brain (Large Enemies, 32 x
# 30) is the big brain's first frame; its second is the same a quarter turn
# round, a pixel off its outline, the new rim a step darker; the small brain
# is each reduced to 16 x 16 (2 x 2 blocks averaged on its tones), the tiny
# one the first reduced to 8 x 8.  The balls on their chains are the two
# beside it: the purple one (palette 4, the fans', has its colours) for six,
# the grey-brown one for Konami's red fourth.  Palette 15 in stage 6 (in
# place of stage 5's): the brain's five tones (its crevice red as 5,1,1: 5,2,1
# reads brown), then the grey ball's.
from PIL import Image as _Im
_LE = _Im.open(D + 'Large Enemies.png').convert('RGB')
_BR = [(192, 56, 40), (208, 96, 152), (232, 112, 208), (232, 208, 224), (232, 232, 232)]
_BR9 = [(5, 1, 1), (6, 3, 4), (6, 3, 6), (7, 6, 7), (7, 7, 7)]
def _brain0():
    g = [[None] * 32 for _ in range(32)]
    for y in range(30):
        for x in range(32):
            p = _LE.getpixel((283 + x, 39 + y))
            if p in _BR: g[y + 1][x] = _BR.index(p)
    return g
def _rot90(g): return [[g[31 - x][y] for x in range(32)] for y in range(32)]
def _peel(g):
    def edge(gg, x, y): return any(not (0 <= x + a < 32 and 0 <= y + c < 32) or gg[y + c][x + a] is None for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1)))
    o = [[None if (g[y][x] is None or edge(g, x, y)) else g[y][x] for x in range(32)] for y in range(32)]
    step = {4: 2, 3: 2, 2: 1, 1: 0, 0: 0}
    return [[step[o[y][x]] if o[y][x] is not None and edge(o, x, y) else o[y][x] for x in range(32)] for y in range(32)]
def _reduce(g, n, cuts=(0.8, 1.55, 2.35, 3.3)):
    W = 32 // n
    o = [[None] * W for _ in range(W)]
    for by in range(W):
        for bx in range(W):
            v = [g[by * n + y][bx * n + x] for y in range(n) for x in range(n)]
            on = [t for t in v if t is not None]
            if len(on) * 2 < len(v): continue
            a = sum(on) / len(on)
            o[by][bx] = sum(a >= c for c in cuts)
    for y in range(W):
        for x in range(W):
            if o[y][x] is not None and any(not (0 <= x + a < W and 0 <= y + c < W) or o[y + c][x + a] is None for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                o[y][x] = min(o[y][x], 0 if (x + y) % 3 else 1)
    return o
def _ball(x0, idx):
    rows = []
    for y in range(16):
        r = ''
        for x in range(16):
            p = _LE.getpixel((x0 + x, 58 + y)) if x < 8 and y < 8 else None
            r += '%X' % idx[nine(p)] if p in _BALLRGB[x0] else '0'
        rows.append(r)
    return rows
_PURPLE = [(136, 192, 224), (136, 64, 176), (96, 40, 112), (136, 96, 192), (56, 32, 56), (152, 224, 224), (248, 248, 248)]
_GREY = [(192, 176, 152), (112, 80, 64), (96, 64, 56), (152, 112, 96), (56, 40, 32), (224, 224, 208), (248, 248, 248)]
_BALLRGB = {323: _PURPLE, 334: _GREY}
_P4 = {}
for _i, _e in enumerate(pal[4]):
    if _i >= 2 and _e != (0, 0): _P4[_e] = _i
_P4idx = {nine(c): _P4[enc(c)] for c in _PURPLE}
_G9 = sorted({nine(c) for c in _GREY} - {(7, 7, 7)}, key=lambda c: (sum(c), c))
_PAL6 = [(0, 0), (0, 0)] + [_enc7(*c) for c in _BR9] + [_enc7(*c) for c in _G9]
_PAL6 += [(0, 0)] * (16 - len(_PAL6))
_G6idx = {c: 7 + i for i, c in enumerate(_G9)}; _G6idx[(7, 7, 7)] = 6
def _rows16(g, x0, y0):
    return [''.join('%X' % (2 + g[y0 + y][x0 + x]) if 0 <= y0 + y < len(g) and 0 <= x0 + x < len(g[0]) and g[y0 + y][x0 + x] is not None else '0' for x in range(16)) for y in range(16)]
_b0 = _brain0(); _b1 = _peel(_rot90(_b0))
stage6 = []
for _g in (_b0, _b1):
    for _q in range(4): stage6.append(_rows16(_g, (_q & 1) * 16, (_q >> 1) * 16))
stage6.append(_rows16(_reduce(_b0, 2), 0, 0)); stage6.append(_rows16(_reduce(_b1, 2), 0, 0))
stage6.append(_rows16(_reduce(_b0, 4), 0, 0))
stage6.append(_ball(323, _P4idx)); stage6.append(_ball(334, _G6idx))
# stage 7's amoeba (4 November 2026; Konami's type 0D: patterns 56-59 as it
# wobbles, 55 when it has stopped, the doughnut; type 14 bursts through 60-63)
# after the arcade's pink cell (Small Enemies, third row): 55 its doughnut
# (8th), 56-59 its 1st, 3rd, 5th and 6th, 60-63 its burst (9th, 10th, the two
# fragments).  In palette 15, which stage 7 loads as STAGE7_PAL15.
_SE = _Im.open(D + 'Small Enemies.png').convert('RGB')
_AM = {55: (132, 147), 56: (7, 20), 57: (41, 54), 58: (77, 92), 59: (96, 111),
       60: (151, 165), 61: (169, 183), 62: (187, 201), 63: (205, 218)}
_am = {}
for _k, (_a, _b) in _AM.items():
    _w = _b - _a + 1
    _am[_k] = [[_SE.getpixel((_a + x, 62 + y)) if 0 <= x < _w and _SE.getpixel((_a + x, 62 + y)) != (255, 0, 255) else None
                for x in range(-((16 - _w) // 2), 16 - (16 - _w) // 2)] for y in range(16)]
_A9 = sorted({nine(p) for g in _am.values() for r in g for p in r if p is not None}, key=lambda c: (sum(c), c))
assert len(_A9) <= 14, _A9
_PAL7 = [(0, 0), (0, 0)] + [_enc7(*c) for c in _A9]
_PAL7 += [(0, 0)] * (16 - len(_PAL7))
for _k, _g in _am.items():
    staged[(7, _k)] = (0xF0, [''.join('%X' % (2 + _A9.index(nine(p))) if p is not None else '0' for p in r) for r in _g])
# palette 4 (the fans', and stage 6's robots in the pool): Konami's robot frames'
# one colour it lacks, a dark orange
_ORANGE = _enc7(5, 2, 1)
assert pal[5][14] == (0, 0)
assert _ORANGE not in pal[4] and pal[4][14] == (0, 0)
pal[4][14] = _ORANGE
pal[5][14] = enc(redify_px((176, 64, 32)))     # and its red twin's (the arcade's orange, 5,2,1)
out =['"""The Next build\'s arcade-style sprites (generated by tools/arcade/gen_art.py;',
       'do not edit by hand).  Konami\'s MSX frames, redrawn after the arcade game\'s',
       'sprites or coloured in their palettes, 4-bit, 16 x 16, a hex digit a pixel',
       '(0 transparent; 1 unused: the Konami colours\' pixel).  Palette bytes:',
       'palette * 16, + 1 for a sprite with a red twin (the next palette), for',
       'those that leave a capsule.  The enemies Konami draws with characters',
       '(the fans, saucers, turrets, capsules) are in the character pool',
       '(spec/nxgfx/pool.bin) with the rest of the stages\' characters."""',
       '# sprite palettes 2-12, 14 and 15: 16 Next 9-bit colours each, (RRRGGGBB, B0)',
       'PALETTES = {']
for k in sorted(pal): out.append('    %d: %r,' % (k, pal[k]))
out.append('}')
out.append("# Konami's sprite patterns replaced: pattern -> (palette byte, rows)")
out.append('SPRITES = {')
for k in sorted(sprites): out.append('    %d: (0x%02X, %r),' % (k, sprites[k][0], sprites[k][1]))
out.append('}')
out.append("# the walkers' 12 patterns (52-63): pattern -> (palette byte, rows)")
out.append('WALKERS = {')
for k in sorted(walkers): out.append('    %d: (0x%02X, %r),' % (k, walkers[k][0], walkers[k][1]))
out.append('}')
out.append("# drawings of Konami's patterns as a later stage loads them: (stage, pattern) ->")
out.append("# (palette byte, rows); a stage gets one wherever its pattern has that content")
out.append('STAGED = {')
for k in sorted(staged): out.append('    %r: (0x%02X, %r),' % (k, staged[k][0], staged[k][1]))
out.append('}')
out.append("# stage 6's brains and balls: patterns 0-3 the big brain's first frame (top")
out.append("# left, top right, bottom left, bottom right), 4-7 its second, 8 and 9 the small")
out.append("# brain's, 10 the tiny one's, 11 the purple ball (palette 4), 12 the grey-brown")
out.append("# one; the others in palette 15, which stage 6 loads as STAGE6_PAL15")
out.append('STAGE6 = [')
for r in stage6: out.append('    %r,' % (r,))
out.append(']')
out.append('STAGE6_PAL15 = %r' % (_PAL6,))
out.append("# stage 7's palette 15 (its amoeba), in place of stage 5's")
out.append('STAGE7_PAL15 = %r' % (_PAL7,))
open(sys.argv[1], 'w').write('\n'.join(out) + '\n')
print('palettes', sorted(pal), 'sprites', len(sprites), 'walkers', len(walkers), 'staged', len(staged))
