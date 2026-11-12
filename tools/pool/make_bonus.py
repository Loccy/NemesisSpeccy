"""One-off (3 November 2026): the bonus stages (9-12) into the Next's artwork,
which had left them out (msx2_pack.py, and the pool built on it, covered
stages 1-8 only).

  make_bonus.py        (writes spec/nxgfx/)

1. The patch's graphics: the patched cartridge's graphics load for stages
   9-12, replayed with msx2_extract.stage_load (checked against openMSX
   captures of the patched cartridge for all four on 3 November 2026: every
   byte the replay writes matches, apart from the characters Konami
   animates, F7 and 78-7D, as for stages 1-8).  Each character the load
   writes becomes a block (as make_pool.py made stages 1-8's); blocks the pool
   lacks are appended to pool.bin (numbered on; no block moves).
2. Our art on top, from stage 2, whose characters the bonus stages share:
   where a bonus character is (pattern and colours) one of stage 2's patched
   characters of that third, and stage 2's block for that character is no
   longer the patch's (our drawings, the arcade bricks, the blank end caps),
   the bonus stage takes stage 2's block.  By content, not number: the patch
   draws some bonus bricks and turret pieces with other numbers (AE, AF its
   45, 46; AA-AD, B0-B5 the turrets' 02-05, 08-0D).
3. The balls (character 44, whose colours are all that tell the four bonus
   stages apart): our arcade sphere (stage 2's block for 44), in each stage's
   colours, in the sphere's own scenery palette values (DA-DD, the bricks
   using D1, D4, D7-D9).
Writes:
  pool.bin           appended;
  maps_bonus.bin     4 x 2K, stages 9-12, in maps.bin's form;
  bonus.bin          the bonus stages' stage file (the four are one once the
                     characters are in the pool), in the stage files' form,
                     cut down to F6 and F7 as make_pool.py cut theirs: the
                     patch's sprites (the bonus stages' own scores at 56-63),
                     stage 2's palette (the patch has none for the bonus
                     stages; stage 2's suits the blocks), the patch's
                     line-colour tables, the mask;
  scenery_bonus.bin  4 x 32: each bonus stage's scenery palette (Layer 2 D1-DF):
                     stage 2's, the sphere's four colours its own."""
import os, sys, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
GFX = os.path.join(ROOT, 'spec', 'nxgfx')
sys.path.insert(0, os.path.join(ROOT, 'spec')); sys.path.insert(0, os.path.join(ROOT, 'local', 'tools', 'msx2'))
import msx2_extract as M
KEEP = (0xF6, 0xF7)
# the spheres' colours, darkest to palest (values DD, DA, DB, DC), RGB 0-7
SPHERE = {9: [(1, 2, 1), (2, 4, 2), (4, 5, 4), (5, 6, 5)],     # green
          10: [(2, 2, 0), (4, 4, 1), (5, 5, 3), (6, 6, 5)],    # yellow
          11: [(0, 1, 3), (1, 3, 5), (3, 4, 6), (5, 5, 7)],    # blue
          12: [(2, 0, 2), (4, 1, 4), (5, 3, 5), (6, 5, 6)]}    # magenta
rom2 = open(os.path.join(ROOT, 'nemmsx2.rom'), 'rb').read()
assert hashlib.sha256(rom2).hexdigest() == M.ROM2_SHA256
pool = bytearray(open(os.path.join(GFX, 'pool.bin'), 'rb').read())
maps = open(os.path.join(GFX, 'maps.bin'), 'rb').read()
st2 = open(os.path.join(GFX, 'stage2.bin'), 'rb').read()
scen = open(os.path.join(GFX, 'scenery.bin'), 'rb').read()
for f in ('maps_bonus.bin', 'bonus.bin', 'scenery_bonus.bin'):
    assert not os.path.exists(os.path.join(GFX, f)), f + ' exists: run once'
n0 = len(pool) // 64
index = {}
for k in range(n0 - 1, -1, -1):
    index[bytes(pool[k * 64:k * 64 + 64])] = k
def written(v, t, c):
    a = t * 0x800 + c * 8
    return all(v.mask[a + i] and v.mask[0x2000 + a + i] for i in range(8))
def raw(v, t, c):
    a = t * 0x800 + c * 8
    return bytes(v[0x2000 + a:0x2000 + a + 8]) + bytes(v[a:a + 8])
def patchblk(v, t, c):
    a = t * 0x800 + c * 8
    return bytes((v[a + r] >> 4) if v[0x2000 + a + r] & (0x80 >> x) else (v[a + r] & 15)
                 for r in range(8) for x in range(8))
def stage2_block(t, c):
    o = 0x800 + (t * 256 + c) * 2
    if not maps[o]: return None
    k = (maps[o] - 66) * 128 + (maps[o + 1] & 0x7F)
    return bytes(pool[k * 64:k * 64 + 64])
def put(blk):
    k = index.get(blk)
    if k is None:
        k = len(pool) // 64; pool.extend(blk); index[blk] = k
    return k
v2 = M.stage_load(rom2, 2)
by_content = {}                         # (third, stage 2 patched character) -> its numbers
for t in range(3):
    for c in range(256):
        if c not in KEEP and written(v2, t, c):
            by_content.setdefault((t, raw(v2, t, c)), []).append(c)
mb = bytearray(4 * 0x800)
files = []; ours = 0; moved = set()
for s in range(9, 13):
    v = M.stage_load(rom2, s)
    for t in range(3):
        for c in range(256):
            if c in KEEP or not written(v, t, c):
                continue
            blk = patchblk(v, t, c)
            if c == 0x44:
                blk = stage2_block(t, 0x44); ours += 1
            else:
                for c2 in sorted(by_content.get((t, raw(v, t, c)), []), key=lambda x: x != c):
                    b2 = stage2_block(t, c2)
                    if b2 is not None and b2 != patchblk(v2, t, c2):
                        blk = b2; ours += 1
                        if c2 != c: moved.add('%d:%02X<-%02X' % (t, c, c2))
                    break
            k = put(blk)
            o = (s - 9) * 0x800 + (t * 256 + c) * 2
            mb[o] = 66 + k // 128; mb[o + 1] = k % 128
    f = bytearray(v[:0x3800])
    m = bytearray(0x700)
    for i in range(0x3800):
        if v.mask[i]:
            m[i >> 3] |= 1 << (i & 7)
    for t in range(3):
        for c in range(256):
            if c in KEEP:
                continue
            for base in (0, 0x2000):
                a = base + t * 0x800 + c * 8
                f[a:a + 8] = bytes(8)
                for i in range(8):
                    m[(a + i) >> 3] &= ~(1 << ((a + i) & 7)) & 0xFF
    f += st2[0x3800:0x3820]                    # stage 2's palette
    f += rom2[0x2E600:0x2E690]                  # the patch's line-colour tables
    assert f[0x3820:0x38B0] == st2[0x3820:0x38B0]
    f += bytes(0x3900 - len(f))
    f += m
    assert len(f) == 0x4000
    files.append(bytes(f))
assert all(x == files[0] for x in files), 'the bonus stage files differ'
sb = bytearray()
for s in range(9, 13):
    p = bytearray(scen[32:64])                 # stage 2's
    for val, (r, g, b) in zip((0xDD, 0xDA, 0xDB, 0xDC), SPHERE[s]):
        o = (val - 0xD0) * 2
        p[o] = (r << 5) | (g << 2) | (b >> 1); p[o + 1] = b & 1
    sb += p
assert len(pool) // 64 <= 6 * 256, 'the pool has outgrown banks 33-38'
open(os.path.join(GFX, 'pool.bin'), 'wb').write(pool)
open(os.path.join(GFX, 'maps_bonus.bin'), 'wb').write(mb)
open(os.path.join(GFX, 'bonus.bin'), 'wb').write(files[0])
open(os.path.join(GFX, 'scenery_bonus.bin'), 'wb').write(sb)
used = sum(1 for i in range(0, len(mb), 2) if mb[i])
print('pool: %d blocks -> %d; bonus maps: %d characters over 4 stages, %d of them ours; by content: %s'
      % (n0, len(pool) // 64, used, ours, ' '.join(sorted(moved))))
