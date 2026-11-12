"""The Vic Viper head-on (the ending's zoom, vv_zoom_make.py), as shapes:
drawn 16 times over and reduced, so every size comes from the same model.
Units are pixels at full size; X from the middle, Y down."""
from PIL import Image, ImageDraw
from collections import Counter
SS = 16
# colours (name -> RGB)
C = dict(
    hull=(236, 232, 220), hull2=(200, 190, 170), hull3=(150, 130, 110), white=(255, 255, 255),
    blue=(60, 90, 200), navy=(20, 40, 120), glass=(80, 200, 255), glass2=(30, 110, 220),
    red=(230, 60, 50), orange=(250, 150, 50), amber=(250, 220, 120), grey=(170, 170, 185))
def mirror(pts): return pts + [(-x, y) for (x, y) in reversed(pts)]
def side(pts): return [pts, [(-x, y) for (x, y) in pts]]
def shapes():
    s = []
    # wings: upper surface, then the blue underside band along the trailing edge
    for w in side([(6, -6), (16, -6), (28, -4.5), (38, -3), (44.5, -4), (44.5, -2.2), (38, 0.2), (28, 3.2), (18, 7), (10, 10), (5, 11)]):
        s.append(('hull', w))
    for w in side([(44.5, -2.6), (38, 0.2), (28, 3.2), (18, 7), (10, 10), (5, 11), (5, 13), (10, 12), (18, 9), (28, 5.2), (38, 1.8), (44, -1.2)]):
        s.append(('blue', w))
    for w in side([(7, -5.5), (16, -5.5), (28, -4), (38, -2.6), (44, -3.4), (38, -1.4), (28, -2.4), (16, -3.6), (7, -3.6)]):
        s.append(('white', w))                       # the leading edge's light
    for w in side([(9, 8.5), (18, 5.6), (28, 2.2), (36, -0.2), (28, 3.0), (18, 6.8), (10, 9.6)]):
        s.append(('hull2', w))                       # shade above the band
    # panel lines
    for a, b in ((( 8, 10), (24, -4.5)), ((14, 8), (30, -4))):
        for sg in (1, -1):
            s.append(('line', ('blue', [(sg * a[0], a[1]), (sg * b[0], b[1])], 0.7)))
    # antennae (the forward prongs, head-on), red tips
    for sg in (1, -1):
        s.append(('line', ('grey', [(sg * 15, -4), (sg * 19.5, -11)], 0.9)))
        s.append(('dot', ('red', (sg * 19.8, -11.6), 1.0)))
    # body
    s.append(('hull', mirror([(3.6, -14), (6.6, -5), (7.4, 3), (5.4, 11), (3.2, 14)])))
    s.append(('hull2', [(6.6, -5), (7.4, 3), (5.4, 11), (4.2, 12), (5.4, 3), (5, -5)]))
    s.append(('hull2', [(-6.6, -5), (-7.4, 3), (-5.4, 11), (-4.2, 12), (-5.4, 3), (-5, -5)]))
    s.append(('navy', mirror([(5.5, 8), (4, 13.5), (2, 15)])))
    s.append(('orange', mirror([(3.6, 8.6), (2.6, 11.4), (1, 12)])))      # the engine glow
    s.append(('amber', mirror([(1.8, 9.2), (0.8, 10.8)])))
    s.append(('red', mirror([(4.6, 6.6), (4.6, 7.6)])))                  # a red line under the canopy
    # canopy
    s.append(('glass2', mirror([(3, -13), (5, -6), (4.4, -3)])))
    s.append(('glass', mirror([(1.8, -12.4), (3.2, -6.4), (2.2, -3.6)])))
    s.append(('white', [(-1, -11.8), (0, -11.8), (-0.6, -8), (-1.6, -8)]))
    # the tail fin
    s.append(('hull', mirror([(1.5, -13.5), (0.8, -29)])))
    s.append(('hull2', [(0.4, -13.5), (1.5, -13.5), (0.8, -29), (0.4, -29)]))
    s.append(('dot', ('red', (0, -30.2), 1.3)))
    # wingtip lights
    for sg in (1, -1):
        s.append(('dot', ('amber', (sg * 44.2, -3.2), 1.1)))
    return s
SWOOP = 6
W, H = 92, 48          # the model's box (pixels at full size), centre at (46, 31)
CX, CY = 46, 31.5
def render(scale):
    """-> (w, h, {(x, y): colour}) at this scale (1: the full size)"""
    w = max(1, int(W * scale + 0.999)); h = max(1, int(H * scale + 0.999))
    im = Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    def P(x, y):
        t = max(0.0, (abs(x) - 10) / 34.5)        # the wings swoop up towards their tips
        y = y - SWOOP * t * t * t
        return ((CX + x) * scale * SS, (CY + y) * scale * SS)
    for kind, v in shapes():
        if kind == 'line':
            col, pts, wd = v
            d.line([P(*p) for p in pts], fill=C[col] + (255,), width=max(1, int(wd * scale * SS)))
        elif kind == 'dot':
            col, (x, y), r = v
            (px, py) = P(x, y); rr = max(r * scale, 0.5) * SS
            d.ellipse((px - rr, py - rr, px + rr, py + rr), fill=C[col] + (255,))
        else:
            d.polygon([P(*p) for p in v], fill=C[kind] + (255,))
    out = {}
    px = im.load()
    for y in range(h):
        for x in range(w):
            cnt = Counter(); n = 0
            for yy in range(SS):
                for xx in range(SS):
                    c = px[x * SS + xx, y * SS + yy]
                    if c[3]: cnt[c[:3]] += 1; n += 1
            if n >= SS * SS * 0.42:
                # the average colour of what covers it
                r = sum(c[0] * k for c, k in cnt.items()) / n; g = sum(c[1] * k for c, k in cnt.items()) / n; b = sum(c[2] * k for c, k in cnt.items()) / n
                out[(x, y)] = (r, g, b)
    return w, h, out
