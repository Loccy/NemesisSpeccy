"""Makes st6_robots.py: stage 6's robots (Konami's type 0C, frames 29-2C,
characters EC-F5) after the arcade game's (Small Enemies, first row, the
8th to 11th sprites; 4 November 2026).  Konami's four frames share their
left half (EC, ED), so all four take the arcade's first frame's left half;
each its own right half.  In palette 4 (the fans', which has the arcade's
colours, plus its dark orange in entry 14), in all three thirds.

  ARCADE_DIR=... st6_robots_make.py > st6_robots.py      (then put_blocks.py 6 st6_robots.py)"""
import os, sys
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'spec'))
import nx_art
D = os.environ['ARCADE_DIR'].rstrip('/') + '/'
sh = Image.open(D + 'Small Enemies.png').convert('RGB')
BG = (255, 0, 255)
XS = [110, 129, 148, 166]
FRAMES = {0x29: (0xEC, 0xEE, 0xED, 0xEF), 0x2A: (0xEC, 0xF0, 0xED, 0xF1),
          0x2B: (0xEC, 0xF2, 0xED, 0xF3), 0x2C: (0xEC, 0xF4, 0xED, 0xF5)}
def nine(c): return tuple(round(v * 7 / 255) for v in c)
def enc(c): r, g, b = nine(c); return ((r << 5) | (g << 2) | (b >> 1), b & 1)
idx = {}
for i, e in enumerate(nx_art.PALETTES[4]):
    if i >= 2: idx.setdefault(e, i)
blocks = {}
for n, (f, chars) in enumerate(sorted(FRAMES.items())):
    def px(x, y):
        p = sh.getpixel((XS[0 if x < 8 else n] + x, 21 + y))
        if p == BG: return 0
        return 0x40 + idx[enc(p)]
    for q, ch in enumerate(chars):
        x0, y0 = 8 * (q & 1), 8 * (q >> 1)
        b = bytes(px(x0 + x, y0 + y) for y in range(8) for x in range(8))
        assert blocks.get(ch, b) == b, hex(ch)
        blocks[ch] = b
print('"""Stage 6\'s robots after the arcade game\'s, Konami\'s characters EC-F5 in all')
print('three thirds (made by st6_robots_make.py, whose docstring says how)."""')
print('BLOCKS = {')
for t in range(3):
    for ch in sorted(blocks):
        print('    (%d, 0x%02X): bytes.fromhex(%r),' % (t, ch, blocks[ch].hex()))
print('}')
