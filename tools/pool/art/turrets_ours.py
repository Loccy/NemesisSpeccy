"""Our turrets in every stage with turrets (3 November 2026).  The pool's
first build (nx_pack_v1.py) gave a stage our turret drawings only where the
turret's characters were stage 1's in all three thirds, so stages 3, 5, 7 and
8 kept the patch's: their middle thirds hold other turret pieces under those
numbers (stages 7, 8) or the red ones throughout (stages 3, 5).

  put_blocks.py STAGE turrets_ours.py      (stages 3, 5, 7, 8)

Konami draws every turret with one design: stage 1's ordinary turret, the
ground one (frames 0F-14, third 2) and the ceiling one (1B-20, third 0), and
the same in red for those that leave a capsule.  Each stage's sets come from
Konami's table at 2:9205 (four rows: capsule ground, ground, capsule ceiling,
ceiling; the script byte's bits 5 and 6 pick the row).  A set takes our
pieces in each third where every frame's image in Konami's own load (nem.rom,
pattern and colours) is stage 1's ordinary turret under one colour map for
the set: the identity (our drawings as stage 1 has them) or the map stage 1's
red turret makes of the ordinary one (our drawings in palette 7, as stage 1's
red ones and stage 2's red ones are).  Stage 1's red ground set (09-0E) is
matched as itself: its fourth frame repeats its fifth.  The colour decides,
not the table row: stage 7's capsule ceiling turrets in the top third share
the ordinary ones' characters and stay blue, as in Konami's game."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'spec'))
import nx_pack as P
STAGE = int(sys.argv[1])
assert STAGE in (3, 5, 7, 8)
rom = open(os.path.join(ROOT, 'nem.rom'), 'rb').read()
maps, pool = P.pool_files()
frames = rom[5 * 0x2000 + 0x11D1:5 * 0x2000 + 0x11D1 + 0x48 * 4]
c4 = lambda f: tuple(frames[4 * f:4 * f + 4])
table = rom[2 * 0x2000 + 0x1205:2 * 0x2000 + 0x1205 + 48]
K1, KS = P.orig_load(rom, 1), P.orig_load(rom, STAGE)
def image(v, t, c):
    a = t * 0x800 + c * 8
    return [(v[a + r] >> 4) if v[0x2000 + a + r] & (0x80 >> x) else (v[a + r] & 15)
            for r in range(8) for x in range(8)]
def colour_map(pairs):
    m = {}
    for a, b in pairs:
        if m.setdefault(a, b) != b:
            return None
    return m
red = lambda b: bytes(0x70 | x & 15 if x >> 4 == 6 else x for x in b)
RED = colour_map((a, b) for i in (0, 1, 2, 4, 5) for x, y in zip(c4(0x0F + i), c4(0x09 + i))
                 for a, b in zip(image(K1, 2, x), image(K1, 2, y)))
BLOCKS = {}
for row in range(4):
    base = table[row * 12 + STAGE - 1]
    if not base:
        continue
    # (stage 1's set, its third, may be the red of it)
    refs = [(0x1B, 0, True)] if row >= 2 else [(0x0F, 2, True), (0x09, 2, False)]
    for t in range(3):
        for ref, rt, may_red in refs:
            m = colour_map((a, b) for i in range(6) for x, y in zip(c4(ref + i), c4(base + i))
                           for a, b in zip(image(K1, rt, x), image(KS, t, y)))
            if m is None:
                continue
            same = all(a == b for a, b in m.items())
            is_red = may_red and not same and all(RED.get(a) == b for a, b in m.items())
            if not (same or is_red):
                continue
            for i in range(6):
                for x, y in zip(c4(ref + i), c4(base + i)):
                    b = P.block(maps, pool, 1, rt, x)
                    assert b is not None and max(b) >= 0x20, (rt, hex(x))
                    b = red(b) if is_red else b
                    assert BLOCKS.get((t, y), b) == b, (STAGE, t, hex(y))
                    BLOCKS[(t, y)] = b
            break
