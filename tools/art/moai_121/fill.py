import pickle
from recolour import scheme, moai, addr
from render import render
from PIL import Image
def fill(scr, names, maxrun=2):
    """In Moai cells holding only yellow and red (the face and its shading),
    a yellow run of up to maxrun pixels with red on both sides, across or down,
    becomes red (looking across cell edges)."""
    s = bytearray(scr)
    W, H = 256, 176
    def cell_ok(r, c):
        return (r // 8, names[r * 32 + c]) in moai and names[r * 32 + c] not in (0xF6, 0xF7)
    def colour(x, y):
        r, c = y // 8, x // 8
        a = s[6144 + r * 32 + c]; b = s[addr(r, c, y % 8)] >> (7 - x % 8) & 1
        return (a & 7) if b else ((a >> 3) & 7)
    def two(r, c):
        a = s[6144 + r * 32 + c]; return {a & 7, (a >> 3) & 7} == {6, 2}
    changed = True; n = 0
    while changed:
        changed = False
        col = [[colour(x, y) for x in range(W)] for y in range(H)]
        for y in range(H):
            for x in range(W):
                r, c = y // 8, x // 8
                if col[y][x] != 6 or not cell_ok(r, c) or not two(r, c): continue
                hit = False
                for dx, dy in ((1, 0), (0, 1)):
                    # the yellow run through (x,y) along this direction
                    a = 0
                    while 0 <= x - (a + 1) * dx < W and 0 <= y - (a + 1) * dy < H and col[y - (a + 1) * dy][x - (a + 1) * dx] == 6: a += 1
                    b = 0
                    while 0 <= x + (b + 1) * dx < W and 0 <= y + (b + 1) * dy < H and col[y + (b + 1) * dy][x + (b + 1) * dx] == 6: b += 1
                    if a + b + 1 > maxrun: continue
                    x0, y0 = x - (a + 1) * dx, y - (a + 1) * dy; x1, y1 = x + (b + 1) * dx, y + (b + 1) * dy
                    if 0 <= x0 < W and 0 <= y0 < H and 0 <= x1 < W and 0 <= y1 < H and col[y0][x0] == 2 and col[y1][x1] == 2:
                        hit = True
                if hit:
                    at = s[6144 + r * 32 + c]; bit = 0x80 >> (x % 8); ad = addr(r, c, y % 8)
                    if at & 7 == 2: s[ad] |= bit        # red is the ink: set the pixel
                    else: s[ad] &= ~bit & 0xFF          # red is the paper: clear it
                    changed = True; n += 1
        # (a pass at a time, so a run that was 3 wide becomes 2 and is taken next pass only if bounded by red)
    return bytes(s), n
if __name__ == '__main__':
    g = {x['dist']: x for x in pickle.load(open('grabs.pkl', 'rb'))}
    tiles = []
    for d in (0x100, 0x160):
        x = g[d]; scr, n = fill(scheme(x['screen'], x['names'], 'A2'), x['names'])
        print('pixels changed', n)
        tiles.append(render(scr, 3).crop((0, 0, 768, 330)))
    sheet = Image.new('RGB', (768, 660))
    for i, t in enumerate(tiles): sheet.paste(t, (0, i * 330))
    sheet.save('moai_A2fill.png')
    sheet.crop((170, 40, 330, 180)).resize((640, 560), Image.NEAREST).save('zoomA2fill.png')
