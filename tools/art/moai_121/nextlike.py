import pickle
from recolour import moai, addr
from grad import colour_map
from render import render
from PIL import Image
DIM = {(t, c) for t in range(3) for c in (0x23, 0xE5)}   # the lying heads' lone bright cell against the rocks (23 hanging, E5 facing up), in whichever third
CHK = [0x55 if y % 2 == 0 else 0xAA for y in range(8)]
def build(x, rocks='solid', ring_ink=1, rock_ink=7, rim=False):
    s = bytearray(x['screen']); names = x['names']; orig = colour_map(x['screen'])
    for r in range(22):
        for c in range(32):
            ch = names[r * 32 + c]
            if (r // 8, ch) not in moai or ch in (0xF6, 0xF7): continue
            a = s[6144 + r * 32 + c]; br = a & 0xC0
            cols = {a & 7, (a >> 3) & 7}
            rows = []
            for y in range(8):
                v = 0
                for b in range(8):
                    o = orig[r * 8 + y][c * 8 + b]
                    on = (o == 5) or (o == 1 and (CHK[y] >> (7 - b)) & 1) \
                         or (o == 3 and (rocks == 'solid' or (CHK[y] >> (7 - b)) & 1 or
                             not all(0 <= c * 8 + b + dx < 256 and 0 <= r * 8 + y + dy < 176 and orig[r * 8 + y + dy][c * 8 + b + dx] == 3
                                     for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))))
                    v = v << 1 | (1 if on else 0)
                rows.append(v)
            if cols & {5, 1}: ink = 6                      # the face: yellow; its shading: yellow and black stippled
            elif 3 in cols: ink = rock_ink                 # the rocks
            else: continue
            if not cols <= {5, 1, 3, 0}:                   # a sprite's ink over the tile: only its paper changes
                pap = (a >> 3) & 7
                s[6144 + r * 32 + c] = (a & 0xC7) | ({5: 6, 1: 6, 3: 7}.get(pap, pap) << 3)
                continue
            if rim and ink == 6:
                px_ = [orig[r * 8 + y][c * 8 + b] for y in range(8) for b in range(8)]
                lit = 5 in px_ and 0 in px_ and 1 not in px_          # the face's lit edge
                mostly = 0 not in px_ and px_.count(5) >= 48          # face and a little shading, no black
                br = 0x40 if (lit or (rim == 2 and mostly)) else 0    # bright yellow
            s[6144 + r * 32 + c] = br | ink                # ink on black paper
            for y in range(8): s[addr(r, c, y)] = rows[y]
    if rim == 2:                       # a bright cell with no bright face cell beside it: dim
        def yel(rr, cc):
            if not (0 <= rr < 22 and 0 <= cc < 32): return None
            ch = names[rr * 32 + cc]
            if (rr // 8, ch) not in moai or ch in (0xF6, 0xF7): return None
            a = s[6144 + rr * 32 + cc]
            return (a & 0x40) if a & 7 == 6 and (a >> 3) & 7 == 0 else None
        lone = [(rr, cc) for rr in range(22) for cc in range(32)
                if yel(rr, cc) and not any(yel(rr + dr, cc + dc) for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
        for rr, cc in lone: s[6144 + rr * 32 + cc] &= 0xBF
        for rr in range(22):           # per-character choices (third, character): dim
            for cc in range(32):
                if (rr // 8, names[rr * 32 + cc]) in DIM and yel(rr, cc): s[6144 + rr * 32 + cc] &= 0xBF
    # the rings: blue, bright
    boxes_ring, boxes_other = set(), set()
    sp = x['sprites']
    for i in range(32):
        yy, xx, p, col = sp[4 * i:4 * i + 4]
        if yy == 0xD0: break
        if yy >= 0xC0: continue
        cells = {(rr, cc) for rr in range((yy + 1) // 8, (yy + 16) // 8 + 1) for cc in range(max(0, xx) // 8, min(255, xx + 15) // 8 + 1)}
        (boxes_ring if p == 252 else boxes_other).update(cells)
    for rr, cc in boxes_ring - boxes_other:
        if rr < 22:
            a = s[6144 + rr * 32 + cc]
            if a & 7 == 2: s[6144 + rr * 32 + cc] = (a & 0xB8) | 0x40 | ring_ink
    return bytes(s)
if __name__ == '__main__':
  g = {x['dist']: x for x in pickle.load(open('grabs2.pkl', 'rb'))}
  for rocks, name in (('solid', 'moai_nextlike.png'), ('edged', 'moai_nextlike_edged.png')):
    tiles = [render(build(g[d], rocks), 3).crop((0, 0, 768, 330)) for d in (0x100, 0x160)]
    sheet = Image.new('RGB', (768, 660))
    for i, t in enumerate(tiles): sheet.paste(t, (0, i * 330))
    sheet.save(name)
