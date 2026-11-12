"""Makes st5_scenery.py: stage 5's scenery reshaded (4 November 2026).  The
patch draws the bones in cream (15), grey-beige (14) and black, shading by
stippling.  Every screen sampled in a ZEsarUX run through stage 5
(st5_screens.z, zlib-packed: the screen's characters, rows 0-21, a 704-byte
record per sample, repeats kept since they weigh the vote) is rebuilt from the character pool; a black pixel with bone on both sides
(left and right, or above and below) is part of the bone's shading, and so is
a small enclosed black group (2-6 pixels, not joined to the background: the
patch's darker shading), which takes a dark step of the ramp, never black;
where the bone is stippled (a pixel unlike its four neighbours, which are
alike in pairs) the tone is smoothed over a 3 x 3 neighbourhood; each shape
is lit from the top left by its own outline; the tone goes on a 9-step ramp,
ivory to a warm brown, in the stage's scenery palette (Layer 2 D1-D9).  Each
character takes, pixel by pixel, the result it gets most often over all its
appearances.  The eggs' blues are left as they are.

  st5_scenery_make.py > st5_scenery.py      (then put_blocks.py 5 st5_scenery.py)

It reads the pool as it stands, so run it before applying, not after."""
import os, sys, zlib
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'spec'))
import nx_pack as P
maps, pool = P.pool_files()
_raw = zlib.decompress(open(os.path.join(HERE, 'st5_screens.z'), 'rb').read())
smp = [{'names': list(_raw[i:i + 704]) + [0] * 64} for i in range(0, len(_raw), 704)]
BONE = {15: 0.95, 14: 0.5}
# the ramp, darkest to lightest, 9-bit (R, G, B 0-7): ivory to a warm
# brown shadow, the patch's two colours (5,5,4) and (7,7,6) on it
RAMP = [(2, 1, 1), (3, 2, 1), (4, 3, 2), (5, 4, 3), (5, 5, 4), (6, 5, 4), (6, 6, 5), (7, 7, 5), (7, 7, 6)]
LIGHT = 0.11
def scene(names):
    """-> grid of (value, third, char, y, x) per pixel, or None off the scenery"""
    g = [[None] * 256 for _ in range(176)]
    for r in range(22):
        t = r // 8
        for c in range(32):
            ch = names[r * 32 + c]
            b = P.block(maps, pool, 5, t, ch)
            if not b or max(b) >= 0x20:
                continue
            for y in range(8):
                for x in range(8):
                    g[r * 8 + y][c * 8 + x] = (b[y * 8 + x], t, ch, y, x)
    return g
def shade(g):
    H, W = 176, 256
    v = lambda y, x: g[y][x][0] if 0 <= y < H and 0 <= x < W and g[y][x] else 0
    inb = lambda y, x: 0 <= y < H and 0 <= x < W and g[y][x] is not None
    # the shape: bone, and black with bone on both sides (its shading)
    shape = [[False] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if not g[y][x]: continue
            p = g[y][x][0]
            if p in BONE or (p == 0 and ((v(y, x - 1) in BONE and v(y, x + 1) in BONE) or (v(y - 1, x) in BONE and v(y + 1, x) in BONE))):
                shape[y][x] = True
    # small enclosed black groups (2-6 pixels, 4-connected, not joined to the
    # open background): the patch's darker shading; part of the shape, given a
    # dark ramp step, never black
    seen = [[False] * W for _ in range(H)]
    clus = set()
    for y in range(H):
        for x in range(W):
            if v(y, x) in BONE or seen[y][x]: continue
            grp = []; stack = [(y, x)]; seen[y][x] = True; big = False
            while stack:
                cy, cx = stack.pop(); grp.append((cy, cx))
                if len(grp) > 6: big = True
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if not (0 <= ny < H and 0 <= nx < W): big = True; continue
                    if v(ny, nx) not in BONE and not seen[ny][nx]:
                        seen[ny][nx] = True; stack.append((ny, nx))
            if not big and len(grp) >= 2 and all(g[cy][cx] for cy, cx in grp):
                clus.update(grp)
                for cy, cx in grp: shape[cy][cx] = True
    S_ = lambda y, x: 0 <= y < H and 0 <= x < W and shape[y][x]
    # stippling: a pixel unlike its four neighbours, which are alike in pairs
    def dith(y, x):
        p = v(y, x)
        return (S_(y, x) and v(y, x - 1) == v(y, x + 1) != p and v(y - 1, x) == v(y + 1, x) != p)
    D = [[dith(y, x) for x in range(W)] for y in range(H)]
    base = lambda p: BONE.get(p, 0.0)
    out = {}
    K = ((-1, -1, 1), (-1, 0, 2), (-1, 1, 1), (0, -1, 2), (0, 0, 4), (0, 1, 2), (1, -1, 1), (1, 0, 2), (1, 1, 1))
    for y in range(H):
        for x in range(W):
            if not shape[y][x]: continue
            if D[y][x] or any(0 <= y + dy < H and 0 <= x + dx < W and D[y + dy][x + dx] for dy, dx, k in K):
                s = w = 0
                for dy, dx, k in K:
                    if S_(y + dy, x + dx):
                        s += base(v(y + dy, x + dx)) * k; w += k
                t = s / w
            else:
                t = base(v(y, x))
            # light from the top left, by the silhouette: 2 pixels in
            lt = sum(1 for d in (1, 2) if not S_(y - d, x - d))
            dk = sum(1 for d in (1, 2) if not S_(y + d, x + d))
            t = t + LIGHT * lt - LIGHT * dk
            t = max(0.0, min(1.0, t))
            lvl = min(len(RAMP) - 1, int(t * len(RAMP)))
            if (y, x) in clus:
                lvl = min(max(lvl, 1), 2)
            out[(y, x)] = 0xD1 + lvl
    return out
votes = defaultdict(Counter)
for s in smp:
    g = scene(s['names'])
    res = shade(g)
    for y in range(176):
        for x in range(256):
            if g[y][x]:
                p, t, ch, yy, xx = g[y][x]
                votes[(t, ch, yy * 8 + xx)][res.get((y, x), p)] += 1
NEW = {}
for (t, ch, i), cnt in votes.items():
    NEW.setdefault((t, ch), bytearray(P.block(maps, pool, 5, t, ch)))[i] = cnt.most_common(1)[0][0]
NEW = {k: bytes(b) for k, b in NEW.items()}
PALETTE = {0xD1 + i: ((r << 5) | (g << 2) | (b >> 1), b & 1) for i, (r, g, b) in enumerate(RAMP)}

if __name__ == '__main__':
    print('"""Stage 5\'s scenery reshaded: the blocks and scenery palette for put_blocks.py,')
    print('made by st5_scenery_make.py (its docstring says how)."""')
    print('BLOCKS = {')
    for (t, ch) in sorted(NEW):
        print('    (%d, 0x%02X): bytes.fromhex(%r),' % (t, ch, NEW[(t, ch)].hex()))
    print('}')
    print('PALETTE = {')
    for v in sorted(PALETTE):
        print('    0x%02X: (0x%02X, %d),' % (v, PALETTE[v][0], PALETTE[v][1]))
    print('}')
