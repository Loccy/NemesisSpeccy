import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import pickle
from render import render
from PIL import Image
moai = set()
for l in open((_NEM + '/spec/native_moai.txt')):
    l = l.strip()
    if l and not l.startswith('#'):
        t, c = l.split(':'); moai.add((int(t), int(c, 16)))
def addr(r, c, y):
    yy = r * 8 + y
    return ((yy & 0xC0) << 5) | ((yy & 7) << 8) | ((yy & 0x38) << 2) | c
CHK = [0x55 if y % 2 == 0 else 0xAA for y in range(8)]
def scheme(scr, names, name):
    s = bytearray(scr)
    for r in range(22):
        for c in range(32):
            if (r // 8, names[r * 32 + c]) not in moai or names[r * 32 + c] in (0xF6, 0xF7): continue
            a = s[6144 + r * 32 + c]; ink, pap, br = a & 7, (a >> 3) & 7, a & 0xC0
            px = [s[addr(r, c, y)] for y in range(8)]
            m = {}
            if name == 'A':  m = {5: 6, 3: 2}                 # yellow faces, blue shading kept, red rocks
            if name == 'A2': m = {5: 6, 1: 2, 3: 2}           # yellow faces, red shading, red rocks
            if name == 'A3': m = {5: 6, 1: 2}                 # yellow faces, red shading, rocks left magenta
            if name == 'A4': m = {5: 6, 1: 2, 3: 4}           # yellow faces, red shading, green rocks
            if name in ('B', 'B2'):
                m = {3: 2, 1: 2}                               # red rocks, red shading
                if {ink, pap} == {5, 1}:                       # face and shading only: orange stipple
                    face = px if ink == 5 else [~b & 0xFF for b in px]
                    px = [face[y] & CHK[y] for y in range(8)]  # half the face pixels yellow, the rest red
                    ink, pap = 6, 2
                else:
                    m[5] = 6 if name == 'B' else 2             # face next to black: yellow (B) or red (B2)
            ink, pap = m.get(ink, ink), m.get(pap, pap)
            s[6144 + r * 32 + c] = br | pap << 3 | ink
            for y in range(8): s[addr(r, c, y)] = px[y]
    return bytes(s)
if __name__ == '__main__':
  g = {x['dist']: x for x in pickle.load(open('grabs.pkl', 'rb'))}
  for name in ('cur', 'A', 'A2', 'B', 'B2'):
    tiles = []
    for d in (0x100, 0x160):
        x = g[d]; scr = x['screen'] if name == 'cur' else scheme(x['screen'], x['names'], name)
        tiles.append(render(scr, 3).crop((0, 0, 768, 330)))
    sheet = Image.new('RGB', (768, 660))
    for i, t in enumerate(tiles): sheet.paste(t, (0, i * 330))
    sheet.save('moai_%s.png' % name)
