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
bank 25, from 2000, our drawings, and bank 26, from 2000, their tables
(art_page()).  Bank 32: the character pool's maps, 2K a stage; banks 33 on:
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
# colour 8).  A stage has a sprite enemy's drawings where all that enemy's
# patterns (SPR_GROUPS: no enemy is drawn half ours, half Konami's) are stage
# 1's both in Konami's own load (nem.rom) and in the stage file.  Build
# switch: NEM_ARC_SPR=0 leaves
# Konami's sprite patterns (and the walkers) as they are.
import nx_art
TAB_PAL, TAB_APAL, TAB_STAGE, TAB_FRAMES = 0x0000, 0x0180, 0x0200, 0x1200
# the explosion, the shot, the pod, the robot, the jet, the materialising
# enemy, the walker (Konami's patterns)
SPR_GROUPS = [range(30, 34), [34], range(35, 40), range(40, 44), range(44, 47), range(47, 51), range(52, 64)]

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
    """data: the stage files (16K a stage).  -> (page 51, page 53, report)"""
    spr = bool(int(os.environ.get('NEM_ARC_SPR', '1')))
    art = bytearray(0x2000); tab = bytearray(0x2000)
    pats = [(k,) + nx_art.SPRITES[k] for k in sorted(nx_art.SPRITES)] + \
           [(k,) + nx_art.WALKERS[k] for k in sorted(nx_art.WALKERS)]
    assert len(pats) <= 40
    assert sorted(k for g in SPR_GROUPS for k in g) == [p[0] for p in pats]
    num = {}
    for i, (k, pal, rows) in enumerate(pats):
        art[i * 128:i * 128 + 128] = nibbles(rows); tab[TAB_APAL + i] = pal; num[k] = i + 1
    for p in range(2, 13):
        o = TAB_PAL + (p - 2) * 28
        tab[o:o + 28] = bytes(b for e in nx_art.PALETTES[p][2:] for b in e)
    assert TAB_PAL + 11 * 28 <= TAB_APAL and TAB_APAL + 40 <= TAB_STAGE
    frames = rom[5 * 0x2000 + 0x11D1:5 * 0x2000 + 0x11D1 + 274]
    tab[TAB_FRAMES:TAB_FRAMES + len(frames)] = frames
    v1 = orig_load(rom, 1); p1 = data[:0x4000]
    sp = lambda v, k: bytes(v[0x1800 + k * 32:0x1800 + k * 32 + 32])
    report = []
    for s in range(1, 9):
        v = orig_load(rom, s); o = TAB_STAGE + (s - 1) * 0x200
        ps = data[(s - 1) * 0x4000:s * 0x4000]
        same = lambda k: sp(v, k) == sp(v1, k) and sp(ps, k) == sp(p1, k)
        on = [k for g in SPR_GROUPS if spr and all(same(k) for k in g) for k in g]
        for k in on:
            tab[o + k] = num[k]
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
    o = 0x4000 + 0x2000
    fires[o:o + len(art)] = art
    o = 2 * 0x4000 + 0x2000
    assert not any(fires[o:o + 0x2000])
    fires[o:o + len(tab)] = tab
    print('our drawings:\n  ' + '\n  '.join(report))
    pool, n = char_pool(maps, pool)
    print('character pool: %d blocks, banks 32-%d' % (n, 31 + len(pool) // 0x4000))
    return bytes(data + fires) + pool

def main():
    rom = open(os.path.join(ROOT, 'nem.rom'), 'rb').read()
    dat = pack(rom)
    open(os.path.join(HERE, 'nx_gfx.dat'), 'wb').write(dat)
    print('spec/nx_gfx.dat (%d bytes)' % len(dat))

if __name__ == '__main__':
    main()
