"""1.2.1: a head or pile character that never turned up in a third in the
captured frames kept 1.2's colours there (a mouth-open hanging head in the
middle third showed a dim cyan character).  Copies the tile from a third
where the character was recoloured, when its pixels are the same there.
The hanging drawings (8, 9, 13) are left out of the bottom third, where
those character numbers are the font.  Adds lines to spec/stage3_tiles.txt."""
import os, sys
NEM = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
PATH = os.path.join(NEM, 'spec', 'stage3_tiles.txt')
rom = open(os.path.join(NEM, 'nem.rom'), 'rb').read()
b1 = lambda a: rom[0x2000 + a - 0x6000]
sys.path.insert(0, os.path.join(NEM, 'spec'))
import native_sets as NS
v = None
m = NS.machine(); m.mem[0xE061] = 2; NS.gfxcap.call(m, 0x422A); m.mem[0xE061] = 3; NS.gfxcap.call(m, 0x422A)
vram = m.vdp.vram
def msx(t, c):                     # Konami's pattern and colour rows for the character
    o = t * 0x800 + c * 8
    return bytes(vram[0x2000 + o:0x2008 + o]) + bytes(vram[o:o + 8])
lines = open(PATH).read().splitlines()
tiles, role = {}, {}
for l in lines:
    f = l.split('#')[0].split()
    if f: t, c = f[0].split(':'); k = (int(t), int(c, 16)); tiles[k] = f[1:10]; role[k] = f[10]
add = []
for dr in range(4, 14):
    h, w = b1(0x6283 + 3 * dr), b1(0x6284 + 3 * dr)
    p = b1(0x6370 + 2 * dr) | b1(0x6371 + 2 * dr) << 8
    for c in sorted({b1(p + i) for i in range(h * w)} - {0}):
        for t in ((0, 1) if dr in (8, 9, 13) else (0, 1, 2)):
            if (t, c) in tiles or (t, c) in dict(add): continue
            src = [s for s in range(3) if (s, c) in tiles and msx(s, c) == msx(t, c)]
            if not src: print('no source for %d:%02X' % (t, c)); continue
            add.append(((t, c), (tiles[(src[0], c)], role[(src[0], c)], src[0])))
for (t, c), (v, r, s) in add: print('%d:%02X from third %d (%s)' % (t, c, s, r))
open(PATH, 'w').write('\n'.join(lines + ['%d:%02X %s  %s' % (t, c, ' '.join(v), r) for (t, c), (v, r, s) in sorted(add)]) + '\n')
print('added', len(add))
