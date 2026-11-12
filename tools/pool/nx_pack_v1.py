"""(Frozen copy of spec/nx_pack.py as of 3 November 2026, before the pool became
the committed artwork; used by make_pool.py.)  The Next build's graphics: packs spec/nxgfx/ (ours, committed) and our
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
patched ROM by tools/msx2/msx2_extract.py (3 November 2026), with our
changes since: stage 1's ground edge in browns (character 43, bottom third,
its top four lines 68, as the patch has it in stage 4).

nx_gfx.dat: banks 16 on.  Banks 16-23: the stage files.  Banks 24-31: each
stage's 64 sprite patterns in fire colours (Next 4-bit, 128 bytes each; edge
pixels 3, one in 4, deeper 5).  Bank 24 also holds, from 2000, the logo;
bank 25, from 2000, our drawings, and bank 26, from 2000, their tables
(art_page()).  Bank 32: the character pool's maps, 2K a stage; banks 33 on:
the pool (char_pool())."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
SPEC = os.path.normpath(os.path.join(HERE, '..', '..', 'spec'))
sys.path.insert(0, HERE); sys.path.insert(1, SPEC)
import extract
GFX = os.path.join(SPEC, 'nxgfx')

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

# Our own drawings (spec/nx_art.py: Konami's enemies redrawn after the arcade
# game's sprites; made by tools/arcade/gen_art.py).  The drawings are in
# bank 25's second 8K (the Next's 8K page 51):
#   0000  the sprite drawings, 128 bytes each: Konami's patterns 30-50, then
#         the walkers' 52-63 (drawing n at (n - 1) * 128; 40 at most)
#   1400  the character enemies' drawings, 128 bytes each (24 at most)
# and the tables in bank 26's second 8K (page 53):
#   0000  sprite palettes 2-12, entries 2-15 (28 bytes each, Next 9-bit)
#   0180  the sprite drawings' palette bytes (drawing n at n - 1)
#   0200  512 bytes a stage: Konami pattern -> sprite drawing (64; 0 none),
#         the number of character enemies' frames (at most 48), and 3 bytes
#         for each: the frame (the object's byte 12: Konami's frame table
#         5:91D1 gives its four characters), palette byte, drawing number
# A sprite's palette byte is palette * 16, + 1 where the next palette is its
# red twin, for the objects that leave a capsule (byte 14 set; Konami's
# colour 8).  A stage has an enemy's drawings where all that enemy's patterns
# or characters (SPR_GROUPS, CHR_GROUPS: no enemy is drawn half ours, half
# Konami's) are stage 1's both in Konami's own load (nem.rom) and in the
# patch's (what the Next shows).  The turrets go by Konami's table of their
# frames (2:9205: a set for each stage on the ground and on the ceiling,
# ordinary and leaving a capsule): a set whose frames have the pixels of
# stage 1's ordinary ones gets the drawings of those, in red (palette 7) for
# those that leave a capsule (Konami's red ones), and otherwise in stage 1's
# colours (6) where the set is stage 1's or in the stage's tint (TURRET_TINT);
# the red ones only in stages whose ordinary ones are ours.
# Build switches: NEM_ARC_SPR=0 leaves Konami's sprite patterns (and the
# walkers) as they are, NEM_ARC_CHR=0 the character enemies.
import nx_art_v1 as nx_art
ART_CHR = 0x1400
TAB_PAL, TAB_APAL, TAB_STAGE = 0x0000, 0x0180, 0x0200
# the explosion, the shot, the pod, the robot, the jet, the materialising
# enemy, the walker (Konami's patterns); the fans, the saucers, the two
# capsules (nx_art.CHARS entries; the turrets are TURRET_*)
SPR_GROUPS = [range(30, 34), [34], range(35, 40), range(40, 44), range(44, 47), range(47, 51), range(52, 64)]
CHR_GROUPS = [range(0, 4), range(4, 9), [21], [22]]
TURRET_GROUND, TURRET_CEILING = 9, 15      # nx_art.CHARS: stage 1's ordinary turrets
TURRET_TINT = {2: 0xB0}                    # stage 2's ordinary turrets in blue (palette 11)

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

def art_page(rom, patched):
    """patched: the patch's stage loads (build()'s data: 16K a stage).
    -> (page 51, page 53, report, each stage's character enemies [(frame,
    palette byte, drawing)])"""
    spr = bool(int(os.environ.get('NEM_ARC_SPR', '1')))
    chr_ = bool(int(os.environ.get('NEM_ARC_CHR', '1')))
    art = bytearray(0x2000); tab = bytearray(0x2000)
    pats = [(k,) + nx_art.SPRITES[k] for k in sorted(nx_art.SPRITES)] + \
           [(k,) + nx_art.WALKERS[k] for k in sorted(nx_art.WALKERS)]
    assert len(pats) <= 40 and len(nx_art.CHARS) <= 24
    assert sorted(k for g in SPR_GROUPS for k in g) == [p[0] for p in pats]
    num = {}
    for i, (k, pal, rows) in enumerate(pats):
        art[i * 128:i * 128 + 128] = nibbles(rows); tab[TAB_APAL + i] = pal; num[k] = i + 1
    for i, (c4, pal, rows) in enumerate(nx_art.CHARS):
        art[ART_CHR + i * 128:ART_CHR + i * 128 + 128] = nibbles(rows)
    for p in range(2, 13):
        o = TAB_PAL + (p - 2) * 28
        tab[o:o + 28] = bytes(b for e in nx_art.PALETTES[p][2:] for b in e)
    assert TAB_PAL + 11 * 28 <= TAB_APAL and TAB_APAL + 40 <= TAB_STAGE
    frames = rom[5 * 0x2000 + 0x11D1:5 * 0x2000 + 0x11D1 + 274]
    c4 = lambda f: tuple(frames[4 * f:4 * f + 4])
    tt = rom[2 * 0x2000 + 0x1205:2 * 0x2000 + 0x1205 + 48]      # 2:9205, 12 stages a variant
    v1 = orig_load(rom, 1); p1 = patched[:0x4000]
    sp = lambda v, k: bytes(v[0x1800 + k * 32:0x1800 + k * 32 + 32])
    def ch(v, c):
        return b''.join(bytes(v[o + t * 0x800 + x * 8:o + t * 0x800 + x * 8 + 8])
                        for x in c for t in range(3) for o in (0, 0x2000))
    def pix(v, c, t):
        return b''.join(bytes(v[0x2000 + t * 0x800 + x * 8:0x2000 + t * 0x800 + x * 8 + 8]) for x in c)
    report = []; stage_ents = {}
    for s in range(1, 9):
        v = orig_load(rom, s); o = TAB_STAGE + (s - 1) * 0x200
        ps = patched[(s - 1) * 0x4000:s * 0x4000]
        same = lambda k: sp(v, k) == sp(v1, k) and sp(ps, k) == sp(p1, k)
        on = [k for g in SPR_GROUPS if spr and all(same(k) for k in g) for k in g]
        for k in on:
            tab[o + k] = num[k]
        ents = []; rep = []
        if chr_:
            chs = lambda i: ch(v, nx_art.CHARS[i][0]) == ch(v1, nx_art.CHARS[i][0]) and \
                            ch(ps, nx_art.CHARS[i][0]) == ch(p1, nx_art.CHARS[i][0])
            for g in CHR_GROUPS:
                if all(chs(i) for i in g):
                    ents += [(f, nx_art.CHARS[i][1], i) for i in g for f in range(len(frames) // 4)
                             if c4(f) == nx_art.CHARS[i][0]]
                    rep.append(str(g[0]) if len(g) == 1 else '%d-%d' % (g[0], g[-1]))
            tur = []
            for var in (1, 3, 0, 2):      # 1, 3: ordinary, on the ground, on the ceiling; 0, 2: red
                base = tt[var * 12 + s - 1]
                if not base:
                    continue
                ceil = var >= 2; red = var in (0, 2)
                ref, rt, d0 = (0x1B, 0, TURRET_CEILING) if ceil else (0x0F, 2, TURRET_GROUND)
                js = []
                for i in range(6):
                    m = [j for j in range(6) for t in range(3)
                         if pix(v, c4(base + i), t) == pix(v1, c4(ref + j), rt)
                         and pix(ps, c4(base + i), t) == pix(p1, c4(ref + j), rt)]
                    js.append(m[0] if m else None)
                if None in js:
                    continue
                if red:
                    if not tur:           # only where the stage's ordinary turrets are ours
                        continue
                    pal = 0x70
                elif all(ch(v, c4(base + i)) == ch(v1, c4(ref + i)) and
                         ch(ps, c4(base + i)) == ch(p1, c4(ref + i)) for i in range(6)):
                    pal = 0x60
                elif s in TURRET_TINT:
                    pal = TURRET_TINT[s]
                else:
                    continue
                tur.append(var)
                ents += [(base + i, pal, d0 + js[i]) for i in range(6)]
                rep.append('turrets %s %s %02X-%02X (palette %d)' % ('ceiling' if ceil else 'ground',
                           'red' if red else 'ordinary', base, base + 5, pal >> 4))
        assert len(ents) <= 48 and len(set(e[0] for e in ents)) == len(ents), (s, ents)
        stage_ents[s] = ents
        tab[o + 64] = len(ents)
        for i, (f, pal, d) in enumerate(ents):
            tab[o + 65 + i * 3:o + 68 + i * 3] = bytes([f, pal, d])
        report.append('stage %d: patterns %s; characters %s' % (s, ','.join(map(str, sorted(on))) or '-',
                                                               ', '.join(rep) or '-'))
    return bytes(art), bytes(tab), report, stage_ents

# The character pool: every character a stage's load writes whole, as an
# 8 x 8 block of Layer 2 pixels (a byte each: the colour number, as lo_cell
# draws it from the pattern and colour copies), each different block once.
# The character enemies drawn as ours (art_page()) are ours here too: in a
# third whose four characters of the frame have the pixels of stage 1's, the
# blocks are our drawing's quarters (top left, top right, bottom left, bottom
# right), each pixel palette * 16 + its value (Layer 2's palette entries
# 20h-CFh: lo_apply loads our sprite palettes 2-12 there too), and where the
# drawing is transparent, the character's own background colour.
# A stage's map (bank 32 + 0x800 * (stage - 1)): 2 bytes for each character
# of each third (third * 256 + character): the 8K page of its block and its
# number in that page (128 a page: 4000 + number * 64), or page 0: none (the
# copies are drawn from).  The stars (F6, F7) twinkle every frame: never
# from the pool.
POOL_BANK = 33
def char_pool(rom, data, stage_ents):
    pool = {}; order = []; maps = bytearray(0x4000)
    frames = rom[5 * 0x2000 + 0x11D1:5 * 0x2000 + 0x11D1 + 274]
    c4 = lambda f: tuple(frames[4 * f:4 * f + 4])
    v1 = data[:0x4000]
    def pix(v, c, t):
        return b''.join(bytes(v[0x2000 + t * 0x800 + x * 8:0x2000 + t * 0x800 + x * 8 + 8]) for x in c)
    def reft(d):                  # the third whose characters show drawing d in stage 1
        return 2 if TURRET_GROUND <= d < TURRET_GROUND + 6 else 0
    for s in range(1, 9):
        v = data[(s - 1) * 0x4000:s * 0x4000]
        m = lambda a: (v[0x3900 + (a >> 3)] >> (a & 7)) & 1
        ours = {}                 # (third, character) -> block
        for f, pal, d in stage_ents[s]:
            rows = nx_art.CHARS[d][2]
            for t in range(3):
                if pix(v, c4(f), t) != pix(v1, nx_art.CHARS[d][0], reft(d)):
                    continue
                for q, c in enumerate(c4(f)):
                    blk = bytearray()
                    for r in range(8):
                        y = (q >> 1) * 8 + r
                        bg = v[t * 0x800 + c * 8 + r] & 15
                        for x in range(8):
                            n = int(rows[y][(q & 1) * 8 + x], 16)
                            blk.append((pal & 0xF0) | n if n else bg)
                    ours[(t, c)] = bytes(blk)
        for t in range(3):
            for c in range(256):
                if c in (0xF6, 0xF7):
                    continue
                a = t * 0x800 + c * 8
                if not all(m(a + i) and m(0x2000 + a + i) for i in range(8)):
                    continue
                blk = ours.get((t, c))
                if blk is None:
                    blk = bytearray()
                    for r in range(8):
                        p, col = v[0x2000 + a + r], v[a + r]
                        blk += bytes(col >> 4 if p & (0x80 >> x) else col & 15 for x in range(8))
                    blk = bytes(blk)
                if blk not in pool:
                    pool[blk] = len(order); order.append(blk)
                k = pool[blk]
                o = (s - 1) * 0x800 + (t * 256 + c) * 2
                maps[o] = POOL_BANK * 2 + k // 128; maps[o + 1] = k % 128
    pages = bytearray(b''.join(order))
    pages += bytes(-len(pages) % 0x4000)
    assert POOL_BANK + len(pages) // 0x4000 <= 48
    return bytes(maps) + bytes(pages), len(order)

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
    art, tab, report, stage_ents = art_page(rom, bytes(data))
    o = 0x4000 + 0x2000
    fires[o:o + len(art)] = art
    o = 2 * 0x4000 + 0x2000
    assert not any(fires[o:o + 0x2000])
    fires[o:o + len(tab)] = tab
    print('our drawings:\n  ' + '\n  '.join(report))
    pool, n = char_pool(rom, data, stage_ents)
    print('character pool: %d blocks, banks 32-%d' % (n, 31 + len(pool) // 0x4000))
    return bytes(data + fires) + pool

def main():
    rom = open(os.path.join(ROOT, 'nem.rom'), 'rb').read()
    dat = pack(rom)
    open(os.path.join(HERE, 'nx_gfx.dat'), 'wb').write(dat)
    print('spec/nx_gfx.dat (%d bytes)' % len(dat))

if __name__ == '__main__':
    main()
