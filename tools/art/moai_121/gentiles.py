import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import pickle, collections, sys
sys.path.insert(0, (_SCRATCH + '/moai')); sys.path.insert(0, (_SCRATCH + '/v121/tree/spec'))
from nextlike import build
from recolour import moai, addr
from grad import colour_map
import tilemodel
rom = open((_NEM + '/nem.rom'), 'rb').read()
shapes = [rom[5*0x2000 + 0x11D1 + 4*i:5*0x2000 + 0x11D1 + 4*i + 4] for i in range(68)]
DRAWN = set()                      # the characters of Konami's head and pile drawings (1:6370, sizes 1:6283)
for dr in range(4, 14):
    b1 = lambda a: rom[0x2000 + a - 0x6000]
    h, w = b1(0x6283 + 3 * dr), b1(0x6284 + 3 * dr); p = b1(0x6370 + 2 * dr) | b1(0x6371 + 2 * dr) << 8
    DRAWN |= {b1(p + i) for i in range(h * w)}
TUR = set()
for b in (0x0F, 0x00, 0x15, 0x1B):
    for c in range(6): TUR.update(shapes[b + c])
tl = pickle.load(open((_SCRATCH + '/v121/s3tiles.pkl'), 'rb'))
def cols(t9):
    a = t9[8]; i, p = a & 7, (a >> 3) & 7
    return {i if t9[r] >> (7 - b) & 1 else p for r in range(8) for b in range(8)}
g = pickle.load(open('grabs3.pkl', 'rb'))
seen = set()
for x in g:
    for k in range(704): seen.add((k // 256, x['names'][k]))
HEAD, ROCK = set(), set()
for k in moai:
    if k not in seen or k[1] in (0xF6, 0xF7) or (k[0] == 2 and k[1] < 0x44): continue
    c = cols(tl[k[0] * 256 + k[1]])
    if c & {1, 5} and c <= {0, 1, 5} and k[1] in DRAWN: HEAD.add(k)   # (not the laser FD or the nuke capsule 77-7A caught on screen)                     # (turret numbers are head pieces in stage 3)
    elif 3 in c and c <= {0, 3} and k[1] not in TUR: ROCK.add(k)      # the turrets' barrels share the rocks' magenta
votes = collections.defaultdict(lambda: [collections.Counter() for _ in range(9)])
for x in g:
    out = build(x, 'edged', ring_ink=5, rock_ink=4, rim=2)
    orig = colour_map(x['screen'])
    for r in range(22):
        for c in range(32):
            k = (r // 8, x['names'][r * 32 + c])
            if k not in HEAD and k not in ROCK: continue
            if not {orig[r*8+y][c*8+b] for y in range(8) for b in range(8)} <= {0, 1, 3, 5}: continue   # a sprite on it
            v = votes[k]
            for y in range(8): v[y][out[addr(r, c, y)]] += 1
            v[8][out[6144 + r * 32 + c]] += 1
tiles = {}; split = []
for k in sorted(HEAD | ROCK):
    if k not in votes: split.append((k, 'no clean view')); continue
    v = votes[k]
    t = [v[i].most_common(1)[0][0] for i in range(9)]
    if any(len(v[i]) > 1 for i in range(9)):
        split.append((k, [dict(v[i]) for i in range(9) if len(v[i]) > 1][:2]))
    rows, attr = tilemodel.invert(t[:8], t[8])          # dense tiles stored the other way round, as the conversion does
    tiles[k] = bytes(list(rows) + [attr])
print('heads', len(HEAD), 'rocks', len(ROCK), 'tiles', len(tiles))
print('occurrences that differed:', len(split))
for s in split[:15]: print(' ', '%d:%02X' % s[0], s[1])
pickle.dump(dict(tiles=tiles, head=HEAD, rock=ROCK), open((_SCRATCH + '/v121/s3new.pkl'), 'wb'))
