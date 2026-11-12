import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, os; sys.path.insert(0, (_NEM + '/spec')); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else HERE)
import extract
from orig_sprites import sprites
from PIL import Image, ImageDraw
D = os.environ['ARCADE_DIR'].rstrip('/') + '/'   # Gradius-Arcade-Assets.zip, unpacked
MG = (255, 0, 255)
q = lambda p: tuple(round(v * 7 / 255) * 255 // 7 for v in p)
SH = {f: Image.open(D + f).convert('RGB') for f in ('Small Enemies.png', 'Large Enemies.png', 'Bosses.png', 'Vic Viper.png')}
def cut(f, box, flip=False, recolour=None, rot=0):
    x0, y0, x1, y1 = box; A = SH[f]; w, h = x1 - x0 + 1, y1 - y0 + 1
    pts = {(c, r) for r in range(h) for c in range(w) if A.getpixel((x0 + c, y0 + r)) != MG}
    t = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    for c, r in pts:
        if any((c + dx, r + dy) in pts for dx in (-1, 0, 1) for dy in (-1, 0, 1) if dx or dy):
            col = q(A.getpixel((x0 + c, y0 + r)))
            if recolour: col = recolour(col)
            t.putpixel((c, r), col + (255,))
    if flip: t = t.transpose(Image.FLIP_TOP_BOTTOM)
    g = Image.new('RGBA', (16, 16), (0, 0, 0, 0)); g.paste(t, ((16 - w) // 2, (16 - h) // 2), t)
    if rot: g = g.rotate(rot)
    return g
# --- originals, straight from nem.rom
n = extract.Nemesis((_NEM + '/nem.rom')); v = n.stage_vram(1); sp = sprites(1)
hi = [0x00,0x00,0x35,0x79,0x4B,0x6F,0xC9,0x5B,0xE9,0xED,0xD5,0xDA,0x35,0xCA,0xDB,0xFF]
lo = [0,0,0,1,1,1,0,1,0,1,0,0,0,1,0,1]
tms = [((h >> 5) * 255 // 7, ((h >> 2) & 7) * 255 // 7, (((h & 3) << 1) | l) * 255 // 7) for h, l in zip(hi, lo)]
def spr(p, colour):
    g = Image.new('RGBA', (16, 16), (0, 0, 0, 0)); b = sp[p*32:p*32+32]
    for r in range(16):
        x = (b[r] << 8) | b[16 + r]
        for c in range(16):
            if x & (0x8000 >> c): g.putpixel((c, r), tms[colour] + (255,))
    return g
def chars(base):
    g = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    for k, (ox, oy) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
        ch = base + k
        for r in range(8):
            p = v[0x2000 + ch * 8 + r]; c = v[ch * 8 + r]
            for b in range(8):
                if p & (0x80 >> b): g.putpixel((ox + b, oy + r), tms[c >> 4] + (255,))
    return g
_tab = open((_NEM + '/nem.rom'), 'rb').read()[5 * 0x2000 + 0x11D1: 5 * 0x2000 + 0x11D1 + 274]
def frame(f):
    # a character enemy's frame f: its four characters from Konami's table (bank 5 at 91D1, 0:48C3)
    g = Image.new('RGBA', (16, 16), (0, 0, 0, 0)); c4 = _tab[4*f:4*f+4]
    for k, (ox, oy) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
        ch = c4[k]
        for r in range(8):
            p = v[0x2000 + ch * 8 + r]; c = v[ch * 8 + r]
            for b in range(8):
                if p & (0x80 >> b): g.putpixel((ox + b, oy + r), tms[c >> 4] + (255,))
    return g
redcore = lambda c: (c[2], c[1] // 2, c[0]) if c[2] > c[0] + 60 else c      # blue core -> red
fan = [cut('Small Enemies.png', (7, 21, 21, 35)), cut('Small Enemies.png', (25, 21, 39, 35)), cut('Small Enemies.png', (43, 22, 57, 36))]
fan.append(fan[0].rotate(90))
_side = cut('Small Enemies.png', (205, 21, 220, 36))
def squash(img, h, rows=(3, 13), flip=False):
    # the side-on pod squashed top to bottom to h rows (nearest), centred where the original frame sits
    b = img.getbbox(); body = img.crop(b)
    t = body.resize((body.width, h), Image.NEAREST)
    if flip: t = t.transpose(Image.FLIP_TOP_BOTTOM)
    g = Image.new('RGBA', (16, 16), (0, 0, 0, 0)); g.paste(t, (b[0], rows[0] + (rows[1] - rows[0] + 1 - h) // 2), t)
    return g
pod = [_side, squash(_side, 11, (3, 13)), squash(_side, 7, (4, 10)), squash(_side, 11, (3, 13), flip=True), _side.transpose(Image.FLIP_TOP_BOTTOM)]
jet = [cut('Small Enemies.png', (7, 43, 22, 58)), cut('Small Enemies.png', (26, 44, 41, 59)), cut('Small Enemies.png', (26, 44, 41, 59), flip=True)]
_c = lambda r, g, b: (r * 255 // 7, g * 255 // 7, b * 255 // 7)
DT, TE, LT, WH, CR, YE, OR, BR = _c(0,3,3), _c(2,5,5), _c(4,6,5), _c(7,7,7), _c(6,6,5), _c(6,6,3), _c(6,3,0), _c(4,2,0)
def robot(p):
    # the MSX robot's own mask (p40-43), coloured by region in the arcade robot's palette
    b = sp[p*32:p*32+32]; g = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    m = [[bool(((b[r] << 8) | b[16 + r]) & (0x8000 >> c)) for c in range(16)] for r in range(16)]
    for r in range(16):
        cs = [c for c in range(16) if m[r][c]]
        for c in cs:
            if r <= 3:                                   # hood
                edge = c in (cs[0], cs[-1])
                if r == 0: col = CR
                elif r == 1: col = TE if edge else WH if c == cs[1] else LT
                elif r == 2: col = TE if edge else YE
                else: col = DT
            elif r <= 10:                                # body and arms
                if c <= 3 or c >= 12: col = OR if r in (6, 7, 8) else BR
                elif 6 <= c <= 9 and r in (7, 8): col = YE if c in (7, 8) else OR
                elif r == 5: col = WH
                elif r == 10: col = TE
                else: col = TE if c >= 9 else LT
            elif r == 11: col = DT                       # waist
            else:                                        # legs
                if 6 <= c <= 9: col = YE if r == 15 else CR
                else: col = BR if r == 15 else OR
            g.putpixel((c, r), col + (255,))
    return g
rob = [robot(p) for p in range(40, 44)]
sau = [cut('Small Enemies.png', b) for b in ((101, 42, 116, 57), (120, 43, 135, 56), (139, 44, 154, 57), (158, 45, 173, 57), (177, 42, 192, 57))]
crab = [cut('Vic Viper.png', (232, 26, 247, 41)), cut('Vic Viper.png', (156, 26, 171, 41))]
R0, R1, R2, R3 = (182, 0, 36), (255, 72, 72), (255, 182, 145), (255, 255, 255)
orb = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
for r, row in enumerate(["..AB..", ".BCCB.", "ACDDCA", "ACDDCA", ".BCCB.", "..AB.."]):
    for c, ch in enumerate(row):
        if ch != '.': orb.putpixel((c, r), {'A': R0, 'B': R1, 'C': R2, 'D': R3}[ch] + (255,))
expl = [cut('Bosses.png', b) for b in ((323, 99, 338, 114), (228, 99, 243, 114), (248, 99, 261, 113), (266, 99, 278, 111))]
_tur = [(7 + 17 * i, 96, 20 + 17 * i, 109) for i in range(13)]
_pick = [0, 2, 4, 8, 10, 12]
tur_g = [cut('Small Enemies.png', _tur[i]) for i in _pick]
tur_c = [cut('Small Enemies.png', _tur[i], flip=True) for i in _pick]
