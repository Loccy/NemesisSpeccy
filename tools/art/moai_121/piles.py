"""1.2.1: the rubble pile a Moai head leaves when destroyed, yellow in every
third.  Konami draws it as drawing 12 on the ground (DC DD over 5E-62 DE) or
drawing 13 hanging from the ceiling (the same, upside down: 26-2A 1C over
1A 1B).  The ground pile's tiles in the middle third (made by gentiles.py)
are copied to the top third, and flipped for the hanging pile in the top and
middle thirds (in the bottom third 1A-2A are other characters).  Adds or
replaces their lines in spec/stage3_tiles.txt."""
import os
NEM = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..')
PATH = os.path.join(NEM, 'spec', 'stage3_tiles.txt')
GROUND = (0xDC, 0xDD, 0xDE, 0x5E, 0x5F, 0x60, 0x61, 0x62)
HANG = dict(zip((0x1A, 0x1B, 0x1C, 0x26, 0x27, 0x28, 0x29, 0x2A), (0xDC, 0xDD, 0xDE, 0x5E, 0x5F, 0x60, 0x61, 0x62)))
lines = open(PATH).read().splitlines()
tiles = {}
for l in lines:
    f = l.split('#')[0].split()
    if f: t, c = f[0].split(':'); tiles[(int(t), int(c, 16))] = [int(x, 16) for x in f[1:10]]
new = {}
for c in GROUND: new[(0, c)] = tiles[(1, c)]
for t in (0, 1):
    for h, g in HANG.items():
        v = tiles[(1, g)]; new[(t, h)] = v[7::-1] + [v[8]]          # upside down, same attribute
out = [l for l in lines if not (l.split() and l[0] != '#' and tuple(int(x, 16) for x in l.split()[0].split(':')) in new)]
out += ['%d:%02X %s  pile' % (t, c, ' '.join('%02X' % x for x in v)) for (t, c), v in sorted(new.items())]
open(PATH, 'w').write('\n'.join(out) + '\n')
print('pile tiles:', len(new))
