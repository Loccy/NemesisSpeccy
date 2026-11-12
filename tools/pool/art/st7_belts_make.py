"""Makes st7_belts.py: stage 7's conveyor belts in the arcade's style on
Konami's characters (4 November 2026).  Every screen of a run through the
belt section (st7_screens.z, zlib-packed: the screen's characters, rows
0-21, a 704-byte record per new distance) is rebuilt from the character pool;
the belt (the characters of BELT) becomes one lilac band with a darker rim
round its outline, and each of the patch's beads (green above and below a
pale middle row) a white hollow ring, the arcade's link (7 x 4), or where the
band is too narrow for it (the curled ends) one smaller ring (6 x 4), moved a
pixel or two if it must.  Each character takes, pixel by pixel: a ring where
most of its appearances have one, the rim where any has it, the band
otherwise (Konami uses the same straight piece with black above in one place
and below in another).  Characters no screen showed are restyled on their own.
The colours go in the stage's scenery palette (D1 rim, D3 band, D4 rings).

  st7_belts_make.py > st7_belts.py      (then put_blocks.py 7 st7_belts.py)

It reads the pool as it stands, so run it before applying, not after."""
import os, sys, zlib
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'spec'))
import nx_pack as P
maps, pool = P.pool_files()
def block(t, ch):
    o = 6 * 2048 + (t * 256 + ch) * 2; pg = maps[o]
    if not pg: return None
    k = (pg - P.POOL_BANK * 2) * 128 + (maps[o + 1] & 0x7f); return pool[k * 64:k * 64 + 64]
BELT = {0: set(range(0x12, 0x27)), 1: set(range(0x42, 0x57)) | set(range(0x59, 0x5F)) | set(range(0xA1, 0xB7)), 2: set()}
BEAD = {2, 3, 7, 12}          # a bead: green above and below its pale middle row
# the new colours: scenery palette D1 on
RIM, EDGE, BAND, RING = 0xD1, 0xD2, 0xD3, 0xD4
NEWPAL = {RIM: (5, 3, 6), EDGE: (6, 5, 7), BAND: (6, 4, 7), RING: (7, 7, 7)}
def screen(ns):
    """pixels (values) of a 176-line screen, and which are belt"""
    W, H = 256, 176
    v = [[0] * W for _ in range(H)]; belt = [[False] * W for _ in range(H)]; cell = [[None] * W for _ in range(H)]
    for r in range(22):
        t = r // 8
        for c in range(32):
            ch = ns[r * 32 + c]; b = block(t, ch)
            if b is None: continue
            isb = ch in BELT[t]
            for y in range(8):
                for x in range(8):
                    v[r * 8 + y][c * 8 + x] = b[y * 8 + x]
                    belt[r * 8 + y][c * 8 + x] = isb and b[y * 8 + x] != 0
                    cell[r * 8 + y][c * 8 + x] = (t, ch) if isb else None
    return v, belt, cell
# the arcade's link (7 x 4); where the band is too narrow for it (the curled
# ends), one smaller ring for all of them: the largest that fits them all
RINGS = [['.XXXXX.', 'XX...XX', 'XX...XX', '.XXXXX.'],
         ['.XXXX.', 'XX..XX', 'XX..XX', '.XXXX.'],
         ['.XXX.', 'X...X', 'X...X', '.XXX.'],
         ['.XXX.', 'X...X', '.XXX.'],
         ['.XX.', 'X..X', '.XX.']]
def restyle(v, belt):
    """the band lilac, its outline the rim colour; at each of the patch's
    beads (a group of green pixels) an arcade link: a 6 x 4 pale ring, the
    band's lilac inside"""
    H, W = len(v), len(v[0])
    # past the screen's edges: as if the belt went on (no rim there)
    m = lambda x, y: not (0 <= x < W and 0 <= y < H) or belt[y][x]
    out = {}
    for y in range(H):
        for x in range(W):
            if not belt[y][x]: continue
            out[(x, y)] = RIM if any(not m(x + a, y + c) for a, c in ((1, 0), (-1, 0), (0, 1), (0, -1))) else BAND
    left = {(x, y) for y in range(H) for x in range(W) if belt[y][x] and v[y][x] in BEAD}
    beads = []
    while left:
        s = [left.pop()]; comp = list(s)
        while s:
            x, y = s.pop()
            for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if n in left: left.remove(n); s.append(n); comp.append(n)
        beads.append((sum(p[0] for p in comp) / len(comp), sum(p[1] for p in comp) / len(comp)))
    def place(ring, cx, cy):
        """where the ring fits inside the band at this bead (moved a pixel or two if it must), or None"""
        w, h = len(ring[0]), len(ring)
        for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0), (1, 1), (1, -1), (-1, 1), (-1, -1), (2, 1), (2, -1)):
            x0 = int(cx) - 4 + (7 - w) // 2 + dx; y0 = int(round(cy - 2)) + (4 - h) // 2 + dy
            if all(out.get((x0 + i, y0 + j)) == BAND for j in range(h) for i in range(w)):
                return x0, y0
        return None
    full = [(b, place(RINGS[0], *b)) for b in beads]
    rest = [b for b, q in full if q is None]
    small = RINGS[1]                    # the smaller ring: 6 x 4
    for ring, cx, cy in [(RINGS[0],) + b for b, q in full if q] + [(small,) + b for b in rest]:
        q = place(ring, cx, cy)
        if q is None: continue
        for j, row in enumerate(ring):
            for i, ch in enumerate(row):
                if ch == 'X': out[(q[0] + i, q[1] + j)] = RING
    return out
def blocks_from(screens):
    """one drawing per (third, character): votes over every screen (edge
    columns left out), the rim where any has it, a ring where most do"""
    votes = defaultdict(lambda: [Counter() for _ in range(64)])
    for ns in screens:
        v, belt, cell = screen(ns)
        new = restyle(v, belt)
        for (x, y), k in new.items():
            if 8 <= x < 248: votes[cell[y][x]][(y % 8) * 8 + x % 8][k] += 1
    def pick(cs):
        if not cs: return None
        n = sum(cs.values())
        if cs[RING] * 2 >= n: return RING
        return RIM if cs[RIM] else BAND
    out = {}
    for key, vs in votes.items():
        b = block(*key)
        out[key] = bytes((pick(cs) if b[i] else 0) or 0 for i, cs in enumerate(vs))
    # belt characters no screen showed (Konami's map does not use them, as
    # far as the run saw): restyled on their own, as if the belt went on
    for t in (0, 1):
        for ch in sorted(BELT[t]):
            b = block(t, ch)
            if (t, ch) in out or b is None: continue
            v = [[b[y * 8 + x] for x in range(8)] for y in range(8)]
            new = restyle(v, [[b[y * 8 + x] != 0 for x in range(8)] for y in range(8)])
            out[(t, ch)] = bytes(new.get((i % 8, i // 8), 0) for i in range(64))
    return out
def module(blocks):
    """put_blocks.py's module text"""
    L = ['"""Stage 7\'s conveyor belts in the arcade\'s style on Konami\'s characters',
         '(made by tools/pool/art/st7_belts_make.py, whose docstring says how)."""',
         'BLOCKS = {']
    for (t, ch), b in sorted(blocks.items()):
        L.append('    (%d, 0x%02X): bytes.fromhex(%r),' % (t, ch, b.hex()))
    L.append('}')
    enc = lambda c: ((c[0] << 5) | (c[1] << 2) | (c[2] >> 1), c[2] & 1)
    L.append('PALETTE = {%s}' % ', '.join('0x%02X: %r' % (k, enc(c)) for k, c in sorted(NEWPAL.items()) if k != EDGE))
    return '\n'.join(L) + '\n'
if __name__ == '__main__':
    raw = zlib.decompress(open(os.path.join(HERE, 'st7_screens.z'), 'rb').read())
    screens = [raw[i:i + 704] + bytes(64) for i in range(0, len(raw), 704)]
    sys.stdout.write(module(blocks_from(screens)))
