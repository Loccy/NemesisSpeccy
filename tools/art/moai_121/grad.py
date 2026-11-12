import pickle
from recolour import scheme, moai, addr
from fill import fill
from render import render
from PIL import Image
NECK = {0x4D, 0x5A}         # the stippled block at the bottom of each head
def colour_map(s):
    out = [[0] * 256 for _ in range(176)]
    for y in range(176):
        for x in range(256):
            r, c = y // 8, x // 8
            a = s[6144 + r * 32 + c]; b = s[addr(r, c, y % 8)] >> (7 - x % 8) & 1
            out[y][x] = (a & 7) if b else ((a >> 3) & 7)
    return out
def setpix(s, x, y, colour):
    r, c = y // 8, x // 8; a = s[6144 + r * 32 + c]; bit = 0x80 >> (x % 8); ad = addr(r, c, y % 8)
    if a & 7 == colour: s[ad] |= bit
    else: s[ad] &= ~bit & 0xFF
DMAX = 4
def make(x, scheme_name='A2', bands=((1, 2), (2, 2), (3, 4), (4, 4))):
    names = x['names']; orig = colour_map(x['screen'])
    s, _ = fill(scheme(x['screen'], names, scheme_name), names)
    s = bytearray(s)
    def face(r, c):
        ch = names[r * 32 + c]; return (r // 8, ch) in moai and ch not in (0xF6, 0xF7)
    for r in range(22):                              # the neck's stipple: red, not yellow
        for c in range(32):
            if face(r, c) and names[r * 32 + c] in NECK:
                a = s[6144 + r * 32 + c]
                s[6144 + r * 32 + c] = (a & 0xC0) | ((2 if (a >> 3) & 7 == 6 else (a >> 3) & 7) << 3) | (2 if a & 7 == 6 else a & 7)
    col = colour_map(s)
    shade = [[col[y][x2] == 2 and orig[y][x2] != 3 and face(y // 8, x2 // 8) for x2 in range(256)] for y in range(176)]
    # only the shading proper: connected areas of 40 pixels or more (not the eyes)
    seen = [[False] * 256 for _ in range(176)]
    for y0 in range(176):
        for x0 in range(256):
            if shade[y0][x0] and not seen[y0][x0]:
                comp = []; st = [(x0, y0)]; seen[y0][x0] = True
                while st:
                    px, py = st.pop(); comp.append((px, py))
                    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                        nx, ny = px+dx, py+dy
                        if 0 <= nx < 256 and 0 <= ny < 176 and shade[ny][nx] and not seen[ny][nx]:
                            seen[ny][nx] = True; st.append((nx, ny))
                if len(comp) < 40:
                    for px, py in comp: shade[py][px] = False
    # distance (4-neighbour) from the shading
    INF = 9; dist = [[0 if shade[y][x2] else INF for x2 in range(256)] for y in range(176)]
    for _ in range(DMAX):
        for y in range(176):
            for x2 in range(256):
                if dist[y][x2] == INF:
                    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                        if 0 <= x2+dx < 256 and 0 <= y+dy < 176 and dist[y+dy][x2+dx] < INF and dist[y+dy][x2+dx] < _ + 1:
                            dist[y][x2] = _ + 1; break
    for y in range(176):
        for x2 in range(256):
            r, c = y // 8, x2 // 8
            if col[y][x2] != 6 or not face(r, c): continue
            a = s[6144 + r * 32 + c]
            if {a & 7, (a >> 3) & 7} != {6, 2}: continue    # red can only go where the cell is yellow and red
            d = dist[y][x2]
            for dd, every in bands:
                if d == dd:
                    # every 2: a checkerboard (orange); every 4: one in four (light orange)
                    on = (x2 + y) % 2 == 0 if every == 2 else (x2 % 2 == 0 and y % 2 == 0)
                    if on: setpix(s, x2, y, 2)
    return bytes(s)
if __name__ == '__main__':
    g = {x['dist']: x for x in pickle.load(open('grabs.pkl', 'rb'))}
    tiles = [render(make(g[d]), 3).crop((0, 0, 768, 330)) for d in (0x100, 0x160)]
    sheet = Image.new('RGB', (768, 660))
    for i, t in enumerate(tiles): sheet.paste(t, (0, i * 330))
    sheet.save('moai_grad.png')
    sheet.crop((170, 40, 330, 180)).resize((640, 560), Image.NEAREST).save('zoom_grad.png')
