"""The Next build's graphics: packs spec/nxgfx/ (ours, committed) and our
drawings of Konami's enemies (spec/nx_art.py) into spec/nx_gfx.dat, the
banks 16-31 of the .NEX (nxbuild.sh).  Needs nem.rom (as every build does)
for Konami's own stage loads, which decide where our drawings apply.

spec/nxgfx/stageN.bin (N = 1-8, 16K each): the stage's graphics as the
Next shows them: video memory 0000-37FF as its stage load leaves it (colours
0000, sprite patterns 1800, characters 2000), its palette at 3800 (16 Next
9-bit colours), the sprite line-colour tables at 3820, and at 3900 a mask (a
bit per byte of 0000-37FF, bit 0 first): set where the load writes the byte.
Bytes it does not write keep whatever was there (as on the MSX2, from
earlier screens).  spec/nxgfx/logo.bin: the title logo, a 4-bit bitmap (256
x 48, 128 bytes a line; lines 16-63 of the title screen), then its palette
(16 Next 9-bit colours).  spec/nxgfx/patches.txt: data bytes in Konami's
own ranges (the font and its colours, object and shot colours, the bosses'
colour tables, map pieces), applied to the .NEX by enh_patch.py.

They began as the graphics of the MSX2 patch "Nemesis - Gradius ENHANCED"
V1.01 (by Victor Martinez and Toni Galvez, based on SHALOM's), read from the
patched ROM by local/tools/msx2/msx2_extract.py (3 November 2026), with our
changes since: stage 1's ground edge in browns (character 43, bottom third,
its top four lines 68, as the patch has it in stage 4).

nx_gfx.dat: banks 16 on.  Banks 16-23: the stage files.  Banks 24-31: each
stage's 64 sprite patterns in fire colours (Next 4-bit, 128 bytes each; edge
pixels 3, one in 4, deeper 5).  Bank 24 also holds, from 2000, the logo;
bank 25, from 2000, our drawings, bank 26, from 2000, their tables
(art_page()), and bank 27, from 2000, the code of nx_tur.asm.  Bank 32: the character pool's maps, 2K a stage; banks 33 on:
the pool (char_pool())."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import extract
GFX = os.path.join(HERE, 'nxgfx')

class Tracked(bytearray):
    """VRAM that remembers which bytes were written."""
    def __init__(self, n):
        super().__init__(n)
        self.mask = bytearray(n)
    def __setitem__(self, k, v):
        if isinstance(k, slice):
            for i in range(*k.indices(len(self))):
                self.mask[i] = 1
        else:
            self.mask[k] = 1
        super().__setitem__(k, v)
    def put(self, a, v, known):
        bytearray.__setitem__(self, a, v)
        self.mask[a] = known

class Patched(extract.Nemesis):
    def __init__(self, rom):
        self.rom = rom
    def decompress(self, vram, bank, address, dst):
        p = address
        def get():
            nonlocal p
            v = self.u8(self.bank_for(p, extract.GFX), p); p += 1
            return v
        while True:
            cmd = get()
            if cmd == 0:
                return dst
            if cmd == 0x80:
                dst = get() | get() << 8
                continue
            if cmd & 0x80:
                for _ in range(cmd & 0x7F):
                    vram[dst & 0x3FFF] = get(); dst += 1
            else:
                v = get()
                for _ in range(cmd):
                    vram[dst & 0x3FFF] = v; dst += 1
    def mirror(self, vram, table, stage, vertical):
        """extract.Nemesis.mirror, but a mirrored byte counts as written only
        where its source was written by this load (Konami copies whatever the
        source character holds)."""
        bank = self.bank_for(table, extract.GFX)
        pointer = self.u16(bank, table + 2 * stage)
        bank = self.bank_for(pointer, extract.GFX)
        while True:
            source = self.u8(bank, pointer)
            if source == 0:
                return
            target = self.u8(bank, pointer + 1)
            flags = self.u8(bank, pointer + 2)
            count = self.u8(bank, pointer + 3)
            third = 0 if flags & 0x04 else (1 if flags & 0x02 else 2)
            src = third * 0x800 + source * 8; size = count * 8
            pat = bytearray(vram[0x2000+src:0x2000+src+size]); pk = vram.mask[0x2000+src:0x2000+src+size]
            col = bytearray(vram[src:src+size]); ck = vram.mask[src:src+size]
            if vertical:
                for i in range(0, size, 8):
                    pat[i:i+8] = pat[i:i+8][::-1]; pk[i:i+8] = pk[i:i+8][::-1]
                    col[i:i+8] = col[i:i+8][::-1]; ck[i:i+8] = ck[i:i+8][::-1]
            else:
                pat = bytearray(int(f'{x:08b}'[::-1], 2) for x in pat)
            for dt, bit in ((0, 0x20), (1, 0x10), (2, 0x08)):
                if flags & bit:
                    dst = dt * 0x800 + target * 8
                    for i in range(size):
                        vram.put(0x2000 + dst + i, pat[i], pk[i])
                        vram.put(dst + i, col[i], ck[i])
            pointer += 4

def fire(p):
    """A TMS 16x16 sprite pattern (32 bytes) -> Next 4-bit, fire colours."""
    rows = [(p[r] << 8) | p[16 + r] for r in range(16)]
    def erode(rs):
        return [rs[y] & (rs[y] << 1) & (rs[y] >> 1) & (rs[y-1] if y else 0)
                & (rs[y+1] if y < 15 else 0) & 0xFFFF for y in range(16)]
    i1 = erode(rows); i2 = erode(i1)
    b = bytearray()
    for y in range(16):
        for x in range(0, 16, 2):
            nib = []
            for xx in (x, x + 1):
                m = 0x8000 >> xx
                nib.append(0 if not rows[y] & m else 5 if i2[y] & m else 4 if i1[y] & m else 3)
            b.append((nib[0] << 4) | nib[1])
    return b

# Our own drawings of Konami's enemies, after the arcade game's sprites.  The
# sprite enemies' are spec/nx_art.py (made by local/tools/arcade/gen_art.py);
# the character enemies' are in the character pool (spec/nxgfx/pool.bin:
# blocks whose pixels are palette * 16 + value, palettes 2-12; the Next
# turns the blocks of an enemy it lifts out of the map into its sprite).  The
# sprite drawings are in bank 25's second 8K (the Next's 8K page 51), 128
# bytes each: Konami's patterns 30-50, then the walkers' 52-63 (drawing n at
# (n - 1) * 128; 40 at most); the tables in bank 26's second 8K (page 53):
#   0000  sprite palettes 2-12, entries 2-15 (28 bytes each, Next 9-bit)
#   0180  the sprite drawings' palette bytes (drawing n at n - 1)
#   0200  512 bytes a stage, its first 64: Konami pattern -> sprite drawing
#         (0 none)
#   1200  Konami's frame table (5:91D1: four characters a frame, the object's
#         byte 12 the frame; top left, top right, bottom left, bottom right)
# A sprite's palette byte is palette * 16, + 1 where the next palette is its
# red twin, for the objects that leave a capsule (byte 14 set; Konami's
# colour 8).  A stage has a sprite enemy's drawings wherever its patterns, in
# Konami's own load (nem.rom), have the contents of the patterns they were
# drawn from, and only when all that enemy's patterns do (SPR_GROUPS,
# STAGED_GROUPS: no enemy is drawn half ours, half Konami's; art_page).  Build
# switch: NEM_ARC_SPR=0 leaves
# Konami's sprite patterns (and the walkers) as they are.
import nx_art
TAB_PAL, TAB_APAL, TAB_STAGE, TAB_FRAMES = 0x0000, 0x0180, 0x0200, 0x1200
TAB_PAL6 = 0x1320                # stage 6's palette 15 (nx_l2.asm TAB_PAL6), after the frames
TAB_PAL7 = 0x1340                # stage 7's (TAB_PAL7)
TAB_BONUS = 0x1400              # the bonus stages' tables (9-12), after the frames
def tab_stage(s):
    return TAB_STAGE + (s - 1) * 0x200 if s <= 8 else TAB_BONUS + (s - 9) * 0x200
# The bonus stages (spec/nxgfx: bonus.bin, their stage file; maps_bonus.bin,
# their maps; scenery_bonus.bin, their scenery palettes): the stage file in
# bank 46, the maps in bank 47 (nx_l2.asm lo_apply)
BONUS_BANK, BONUS_MAPS_BANK = 46, 47
TUR_PAGE = 55                   # nx_tur.asm's 8K page (bank 27's second half)
ART2_PAGE = 57                  # our drawings 65 on (bank 28's second half; nx_l2.asm LO_ART2)
# stage 8's electricity (nx_st8.py, made by local/tools/pool/art/st8_brain_make.py)
# in bank 29's second half, which nx_tur.asm maps at 4000 (nx_tur.asm S8_*):
#   0000  the drawings, 128 bytes each (4-bit), sent to patterns 104-127, then
#         86 on (S8_PATNO)
#   1000  the sprites: their number, then each one's bolt (0-5), X, Y and
#         pattern (as tu_put takes it: the pattern - 104, mod 256)
#   1100  the sockets' objects: X, Y for each bolt
#   1200  palettes 14 and 15, entries 2-15 (28 bytes each, Next 9-bit)
#   1300  the number of drawings
S8_PAGE = 59
# the ending's Vic Viper zoom (nx_vvzoom.py, made by local/tools/arcade/vv_zoom_make.py)
# in banks 30 and 31's second halves, which nx_tur.asm maps at 4000 (VV_*):
#   page 61  0000  the size for each tick of the zoom (176)
#            00C0  each size: its first drawing, its number of drawings
#            00E0  palette 15, entries 2-15 (28 bytes, Next 9-bit)
#            0100  each drawing's sprite: X, Y
#            0200  the drawings, 128 bytes each (4-bit): 0-59 here, the
#                  rest from page 63's 0000
VV_PAGES = (61, 63)
# the Big Core in the arcade's drawing (nx_bigcore.py, made by
# local/tools/arcade/bigcore_make.py) in bank 41's first half, which nx_tur.asm
# maps at 4000 (BC_*): 0000 its 44 drawings (the 20 blocks that never change,
# then the wall blocks for walls 0-5), 1600 its five cores, 1900 palettes 14
# and 15 (entries 2-15, 28 bytes each)
BC_PAGE = 82
S8_PATNO = [104 + i for i in range(24)] + [86 + i for i in range(10)]
# the explosion, the shot, the pod, the robot, the jet, the materialising
# enemy, the walker (Konami's patterns)
SPR_GROUPS = [range(30, 34), [34], range(35, 40), range(40, 44), range(44, 47), range(47, 51), range(52, 64)]
# and those of later stages' own patterns (nx_art.STAGED): stage 3's disc, its
# wheel; stage 5's crescents, star, balls (the clusters and the singles), claws
STAGED_GROUPS = [[(3, k) for k in range(47, 51)], [(3, k) for k in range(55, 59)],
                 [(5, k) for k in range(40, 44)], [(5, 51)], [(5, k) for k in range(52, 60)],
                 [(5, k) for k in range(60, 64)],
                 [(7, k) for k in range(55, 60)], [(7, k) for k in range(60, 64)]]   # stage 7's amoeba, its burst
NART = 90                       # drawings at most (nx_l2.asm NART, LO_APAL); 1-64 in page 51, 65 on in page 57
PALS = list(range(2, 13)) + [14, 15]   # our sprite palettes (13 is the ship's), in TAB_PAL in this order

def orig_load(rom, s):
    """VRAM (colours 0000, sprite patterns 1800, patterns 2000) after Konami's
    own stage load in nem.rom: the characters and sprites only."""
    n = Patched(rom); v = Tracked(0x4000)
    n.load_records(v, 0x932D)
    n.load_records(v, n.u16(5, 0x92E3 + 2 * s))
    n.mirror(v, 0x92FB, s, False)
    n.mirror(v, 0x9313, s, True)
    n.decompress(v, 5, 0x86BB, 0x1800)
    t = 0x42AD + 6 * s
    for k in range(2):
        src = n.u16(0, t + 3 * k); ch = n.u8(0, t + 3 * k + 2)
        n.decompress(v, n.bank_for(src, extract.GFX), src, 0x1800 + ch * 8)
    if s == 5:
        n.decompress(v, n.bank_for(0x8FCB, extract.GFX), 0x8FCB, 0x1D00)
    return v

def nibbles(rows):
    return bytes(int(r[x], 16) << 4 | int(r[x + 1], 16) for r in rows for x in range(0, 16, 2))

# The character pool (spec/nxgfx: pool.bin, maps.bin), the stages' characters
# as 8 x 8 blocks of Layer 2 pixels (a byte each: the stage's colours 0-15,
# our drawings' palette * 16 + value), each different block once; for each
# stage (maps.bin, 2K each) 2 bytes for each character of each third (third *
# 256 + character): the 8K page of its block in the .NEX and its number in
# that page (128 a page: 4000 + number * 64), or page 0: none (lo_cell draws
# it from the copies).  Packed as bank 32 (the maps, with bit 7 of the number
# set for a block of our drawings) and banks 33 on.
POOL_BANK = 33
def pool_files():
    maps = open(os.path.join(GFX, 'maps.bin'), 'rb').read()
    pool = open(os.path.join(GFX, 'pool.bin'), 'rb').read()
    assert len(maps) == 0x4000 and len(pool) % 64 == 0
    return maps, pool

def block(maps, pool, s, t, c):
    o = (s - 1) * 0x800 + (t * 256 + c) * 2
    if not maps[o]:
        return None
    k = (maps[o] - POOL_BANK * 2) * 128 + maps[o + 1]
    return pool[k * 64:k * 64 + 64]

def art_page(rom, data, maps, pool):
    """data: the stage files (16K a stage).  -> (page 51, page 53, report)
    A drawing is of one of Konami's patterns as a stage loads it (nx_art:
    SPRITES and WALKERS stage 1's, STAGED a later stage's); a stage gets it in
    every slot whose pattern (Konami's own load) has that content, for a group
    (one enemy's patterns: no enemy drawn half ours, half Konami's) only when
    every pattern of the group is there."""
    spr = bool(int(os.environ.get('NEM_ARC_SPR', '1')))
    art = bytearray(0x4000); tab = bytearray(0x2000)       # art: pages 51 and 57
    pats = [((1, k),) + nx_art.SPRITES[k] for k in sorted(nx_art.SPRITES)] + \
           [((1, k),) + nx_art.WALKERS[k] for k in sorted(nx_art.WALKERS)] + \
           [(sk,) + nx_art.STAGED[sk] for sk in sorted(nx_art.STAGED)]
    assert len(pats) <= NART
    groups = [[(1, k) for k in g] for g in SPR_GROUPS] + STAGED_GROUPS
    assert sorted(sk for g in groups for sk in g) == sorted(p[0] for p in pats)
    num = {}
    for i, (sk, pal, rows) in enumerate(pats):
        art[i * 128:i * 128 + 128] = nibbles(rows); tab[TAB_APAL + i] = pal; num[sk] = i + 1
    for i, p in enumerate(PALS):
        o = TAB_PAL + i * 28
        tab[o:o + 28] = bytes(b for e in nx_art.PALETTES[p][2:] for b in e)
    assert sorted(nx_art.PALETTES) == PALS
    assert TAB_PAL + len(PALS) * 28 <= TAB_APAL and TAB_APAL + NART <= TAB_STAGE
    # stages 6 and 7's palette 15 (lo_pal1415), after Konami's frames
    for o, pal in ((TAB_PAL6, nx_art.STAGE6_PAL15), (TAB_PAL7, nx_art.STAGE7_PAL15)):
        assert TAB_FRAMES + 274 <= o and o + 28 <= TAB_BONUS
        tab[o:o + 28] = bytes(b for e in pal[2:] for b in e)
    assert NART * 128 <= len(art)
    frames = rom[5 * 0x2000 + 0x11D1:5 * 0x2000 + 0x11D1 + 274]
    tab[TAB_FRAMES:TAB_FRAMES + len(frames)] = frames
    loads = {s: orig_load(rom, s) for s in range(1, 13)}
    sp = lambda v, k: bytes(v[0x1800 + k * 32:0x1800 + k * 32 + 32])
    report = []
    for s in range(1, 13):
        v = loads[s]; o = tab_stage(s)
        on = {}
        for g in groups:
            slots = {sk: [k for k in range(64) if sp(v, k) == sp(loads[sk[0]], sk[1])] for sk in g}
            if spr and all(slots.values()):
                for sk, ks in slots.items():
                    for k in ks:
                        assert on.get(k, num[sk]) == num[sk], (s, k)
                        on[k] = num[sk]
        for k, n in on.items():
            tab[o + k] = n
        assert not any(tab[o:o + 10])       # lo_tur reads LO_OVR's first 10 bytes as 0
        report.append('stage %d: patterns %s' % (s, ','.join(map(str, sorted(on))) or '-'))
    return bytes(art), bytes(tab), report

def char_pool(maps, pool):
    maps = bytearray(maps)
    for o in range(0, 0x4000, 2):
        if maps[o]:
            k = (maps[o] - POOL_BANK * 2) * 128 + maps[o + 1]
            if max(pool[k * 64:k * 64 + 64]) >= 0x20:
                maps[o + 1] |= 0x80       # a block of our drawings
    pages = bytearray(pool)
    pages += bytes(-len(pages) % 0x4000)
    assert POOL_BANK + len(pages) // 0x4000 <= 48
    return bytes(maps) + bytes(pages), len(pool) // 64

# Stage 6's brains (Konami's boss 2: brains at E790 and E7C0, each with up to
# two chains of seven balls at +10h and +20h, drawn as characters from bank
# 10's tables AAA6 and AAB0) shown as sprites by nx_tur.asm: its tables at
# TB6 in page 55, after its code.  Our patterns (nx_art.STAGE6, 13), then
# for each of the five brain drawings its size in characters and its sprites
# (X, Y, pattern; four at most), for each of the 40 chain drawings its size
# and its balls' top left corners, in order along the chain from the end at
# the brain (the red one fourth).
TB6 = 0x1600                    # in the page (6000 + 1600 = 7600: nx_tur.asm TB)
def stage6_tables(rom):
    v = orig_load(rom, 6)
    def u8(bank, a): return rom[bank * 0x2000 + (a & 0x1FFF)]
    def entry(base, i):
        p = u8(10, base + 2 * i) | u8(10, base + 2 * i + 1) << 8
        W, H = u8(10, p), u8(10, p + 1)
        return W, H, [u8(10, p + 3 + k) for k in range(W * H)]
    def render(W, H, cs, third=1):
        g = [[0] * (W * 8) for _ in range(H * 8)]
        for r in range(H):
            for c in range(W):
                ch = cs[r * W + c]
                if not ch: continue
                for y in range(8):
                    pat = v[0x2000 + third * 0x800 + ch * 8 + y]; col = v[third * 0x800 + ch * 8 + y]
                    for x in range(8):
                        g[r * 8 + y][c * 8 + x] = (col >> 4) if pat & (0x80 >> x) else (col & 15)
        return g
    out = bytearray()
    for rows in nx_art.STAGE6:
        out += nibbles(rows)
    assert len(out) == 13 * 128
    def bbox_c(pts):
        xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
        return (min(xs) + max(xs) + 1) / 2, (min(ys) + max(ys) + 1) / 2
    brs = bytearray(); dims = bytearray()
    for i in range(5):
        W, H, cs = entry(0xAAA6, i)
        dims += bytes([W, H])
        if i < 2:
            spr = [(16 * (q & 1), 16 * (q >> 1), 4 * i + q) for q in range(4)]
        else:
            g = render(W, H, cs)
            kc = bbox_c([(x, y) for y in range(len(g)) for x in range(len(g[0])) if g[y][x]])
            n = 8 + i - 2
            rows = nx_art.STAGE6[n]
            oc = bbox_c([(x, y) for y in range(16) for x in range(16) if rows[y][x] != '0'])
            spr = [(int(round(kc[0] - oc[0])), int(round(kc[1] - oc[1])), n)]
        b = bytes([len(spr)]) + b''.join(bytes([x & 255, y & 255, n]) for x, y, n in spr)
        brs += b + bytes(13 - len(b))
    T = [u8(2, 0x8377 + d) for d in range(40)]
    T = [t - 256 if t > 127 else t for t in T]
    tpl = None
    chd = bytearray(); chb = bytearray()
    for d in range(40):
        W, H, cs = entry(0xAAB0, d)
        g = render(W, H, cs)
        left = {(x, y) for y in range(len(g)) for x in range(len(g[0])) if g[y][x]}
        if tpl is None:             # a ball: the first drawing's top one, as an 8 x 8 mask
            x0, y0 = min(left, key=lambda q: (q[1], q[0]))
            comp = []; st = [(x0, y0)]; seen = {(x0, y0)}
            while st:
                q = st.pop(); comp.append(q)
                for n in ((q[0] + 1, q[1]), (q[0] - 1, q[1]), (q[0], q[1] + 1), (q[0], q[1] - 1)):
                    if n in left and n not in seen and abs(n[1] - y0) < 8: seen.add(n); st.append(n)
            bx = min(q[0] for q in comp); by = min(q[1] for q in comp)
            tpl = sorted(((x - bx, y - by) for x, y in comp), key=lambda q: (q[1], q[0]))
            assert len(tpl) == 47, len(tpl)
        balls = []
        while left:
            fx, fy = min(left, key=lambda q: (q[1], q[0]))
            ox, oy = fx - tpl[0][0], fy - tpl[0][1]
            cells = [(ox + a, oy + c) for a, c in tpl]
            assert all(q in left for q in cells), d
            for q in cells: left.remove(q)
            balls.append((ox, oy, sum(g[y][x] in (6, 8) for x, y in cells) > 20))
        assert len(balls) == 7 and sum(b[2] for b in balls) == 1, d
        # the brain's centre from this drawing's top left, as Konami places it
        # (2:8308; the big brain): above it for drawings 0-9 and 30-39 (the
        # chain at +10h), below for 10-29 (+20h)
        if d < 10 or d >= 30: bc = (8 - T[d], H * 8 + 16)
        else: bc = (8 - T[d], -16)
        dist = lambda b, q: (b[0] + 4 - q[0]) ** 2 + (b[1] + 4 - q[1]) ** 2
        path = [min(balls, key=lambda b: dist(b, bc))]
        while len(path) < 7:
            last = path[-1]
            path.append(min((b for b in balls if b not in path), key=lambda b: dist(b, (last[0] + 4, last[1] + 4))))
        assert path[3][2], (d, path)
        chd += bytes([W, H])
        chb += b''.join(bytes([x, y]) for x, y, _ in path)
    out += dims + bytes(6) + brs
    assert len(out) == 0x690 + 65
    out += bytes(0x6E0 - len(out)) + chd
    out += bytes(0x730 - len(out)) + chb
    assert len(out) == 0x730 + 560
    return bytes(out)

def pack(rom):
    """-> nx_gfx.dat (bytes) from spec/nxgfx and nem.rom."""
    data = bytearray()
    for s in range(1, 9):
        b = open(os.path.join(GFX, 'stage%d.bin' % s), 'rb').read()
        assert len(b) == 0x4000, s
        data += b
    logo = open(os.path.join(GFX, 'logo.bin'), 'rb').read()
    assert len(logo) == 0x1800 + 32
    fires = bytearray()
    for s in range(1, 9):
        v = data[(s - 1) * 0x4000:s * 0x4000]
        f = bytearray()
        for n in range(64):
            f += fire(v[0x1800 + 32*n:0x1800 + 32*n + 32])
        if s == 1:
            f += bytes(0x2000 - len(f)) + logo
        fires += f + bytes(0x4000 - len(f))
    # bank 25's second 8K: our own drawings, bank 26's their tables (art_page)
    maps, pool = pool_files()
    art, tab, report = art_page(rom, bytes(data), maps, pool)
    # each stage's scenery palette (Layer 2 entries D1-DF, for the pool's
    # blocks in values D1-DF): 32 bytes a stage, at its table + 40h
    scen = open(os.path.join(GFX, 'scenery.bin'), 'rb').read()
    assert len(scen) == 8 * 32
    scen += open(os.path.join(GFX, 'scenery_bonus.bin'), 'rb').read()
    assert len(scen) == 12 * 32
    tab = bytearray(tab)
    for s in range(1, 13):
        o = tab_stage(s) + 0x40
        assert not any(tab[o:o + 32])
        tab[o:o + 32] = scen[(s - 1) * 32:s * 32]
    assert TAB_FRAMES + 274 <= TAB_BONUS and TAB_BONUS + 4 * 0x200 <= 0x2000
    tab = bytes(tab)
    o = 0x4000 + 0x2000
    fires[o:o + 0x2000] = art[:0x2000]
    o = ART2_PAGE // 2 * 0x4000 - 24 * 0x4000 + 0x2000     # drawings 65 on
    assert ART2_PAGE % 2 and not any(fires[o:o + 0x2000])
    fires[o:o + 0x2000] = art[0x2000:]
    o = 2 * 0x4000 + 0x2000
    assert not any(fires[o:o + 0x2000])
    fires[o:o + len(tab)] = tab
    # bank 27's second 8K (page 55): stage 5's turrets and skeletons and the
    # shots over the scenery, code assembled at 6000 (nx_tur.asm; nx_l2.asm
    # LO_TURP)
    tur = open(os.path.join(HERE, 'nx_tur.bin'), 'rb').read()
    sym = open(os.path.join(HERE, 'nx_low.sym')).read()
    assert 'LO_TURP: EQU 0x%08X' % TUR_PAGE in sym
    o = (TUR_PAGE // 2 - 24) * 0x4000 + 0x2000
    assert TUR_PAGE % 2 and len(tur) <= TB6 and not any(fires[o:o + 0x2000])
    fires[o:o + len(tur)] = tur
    import nx_st8
    o8 = (S8_PAGE // 2 - 24) * 0x4000 + 0x2000
    assert S8_PAGE % 2 and not any(fires[o8:o8 + 0x2000])
    assert len(nx_st8.PATS) <= len(S8_PATNO) and len(nx_st8.SOCKETS) == 6
    for i, rows in enumerate(nx_st8.PATS):
        fires[o8 + i * 128:o8 + i * 128 + 128] = bytes.fromhex(''.join(rows))
    spr = bytes([len(nx_st8.SPR)]) + bytes(b for (n, x, y, k) in nx_st8.SPR for b in (n, x, y, (S8_PATNO[k] - 104) & 255))
    fires[o8 + 0x1000:o8 + 0x1000 + len(spr)] = spr
    fires[o8 + 0x1100:o8 + 0x110C] = bytes(b for xy in nx_st8.SOCKETS for b in xy)
    fires[o8 + 0x1300] = len(nx_st8.PATS)
    for k, pal in enumerate((nx_st8.PAL14, nx_st8.PAL15)):
        fires[o8 + 0x1200 + k * 28:o8 + 0x1200 + k * 28 + 28] = bytes(b for e in pal[2:] for b in e)
    import nx_vvzoom as vz
    o61, o63 = [(p // 2 - 24) * 0x4000 + 0x2000 for p in VV_PAGES]
    assert all(p % 2 for p in VV_PAGES) and not any(fires[o61:o61 + 0x2000]) and not any(fires[o63:o63 + 0x2000])
    assert len(vz.TABLE) <= 0xC0 and len(vz.FRAMES) <= 16
    fires[o61:o61 + len(vz.TABLE)] = bytes(vz.TABLE)
    k = 0; pos = b''
    for i, spr in enumerate(vz.FRAMES):
        fires[o61 + 0xC0 + 2 * i:o61 + 0xC2 + 2 * i] = bytes([k, len(spr)])
        for (x, y, rows) in spr:
            ov = o61 + 0x200 + k * 128 if k < 60 else o63 + (k - 60) * 128
            fires[ov:ov + 128] = bytes.fromhex(''.join(rows))
            pos += bytes([x & 255, y & 255]); k += 1
    assert k <= 60 + 64 and len(pos) <= 0x100
    fires[o61 + 0x100:o61 + 0x100 + len(pos)] = pos
    fires[o61 + 0xE0:o61 + 0xE0 + 28] = bytes(b for e in vz.PAL15[2:] for b in e)
    t6 = stage6_tables(rom)
    assert TB6 + len(t6) <= 0x2000
    fires[o + TB6:o + TB6 + len(t6)] = t6
    print('our drawings:\n  ' + '\n  '.join(report))
    pool, n = char_pool(maps, pool)
    print('character pool: %d blocks, banks 32-%d' % (n, 31 + len(pool) // 0x4000))
    out = bytearray(data + fires) + pool
    assert 16 + len(out) // 0x4000 <= BONUS_BANK
    out += bytes((BONUS_BANK - 16) * 0x4000 - len(out))
    import nx_bigcore as bc
    ob = (BC_PAGE // 2 - 16) * 0x4000
    assert not BC_PAGE % 2 and 16 + (len(data) + len(fires) + len(pool)) // 0x4000 <= BC_PAGE // 2 and not any(out[ob:ob + 0x2000])
    assert len(bc.TILES) == 44 and len(bc.CORES) == 5
    for i, rows in enumerate(bc.TILES + bc.CORES):
        out[ob + i * 128:ob + i * 128 + 128] = bytes.fromhex(''.join(rows))
    for k, pal in enumerate((bc.PAL14, bc.PAL15)):
        out[ob + 0x1900 + k * 28:ob + 0x1900 + k * 28 + 28] = bytes(b for e in pal[2:] for b in e)
    bonus = open(os.path.join(GFX, 'bonus.bin'), 'rb').read()
    assert len(bonus) == 0x4000
    out += bonus
    mb = bytearray(open(os.path.join(GFX, 'maps_bonus.bin'), 'rb').read())
    assert len(mb) == 4 * 0x800
    for o in range(0, len(mb), 2):
        if mb[o]:
            k = (mb[o] - POOL_BANK * 2) * 128 + mb[o + 1]
            assert k < n
            if max(pool[0x4000 + k * 64:0x4000 + k * 64 + 64]) >= 0x20:
                mb[o + 1] |= 0x80       # a block of our drawings
    out += mb + bytes(0x4000 - len(mb))
    assert 16 + len(out) // 0x4000 == BONUS_MAPS_BANK + 1
    print('bonus stages: stage file bank %d, maps bank %d' % (BONUS_BANK, BONUS_MAPS_BANK))
    return bytes(out)

def main():
    rom = open(os.path.join(ROOT, 'nem.rom'), 'rb').read()
    dat = pack(rom)
    open(os.path.join(HERE, 'nx_gfx.dat'), 'wb').write(dat)
    print('spec/nx_gfx.dat (%d bytes)' % len(dat))

if __name__ == '__main__':
    main()
