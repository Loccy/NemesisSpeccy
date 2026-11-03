"""The MSX2 graphics pack for the Next build, read from the user's own files.

The user supplies nem.rom (as for every build) and the "Nemesis - Gradius
ENHANCED" V1.01 IPS (in the project root, under its own name); neither is
distributed.  This script:

  1. applies the IPS to nem.rom -> nemmsx2.rom (both checked by SHA-256);
  2. replays the patched cartridge's stage graphics load (0:422A) for each
     stage, statically, with extract.py's replay of Konami's loader (the
     patch keeps Konami's loader and data format; it changes the data, the
     status-line font routine at 0:58BA and the sprite load, which it sends
     through its own code: Konami's block at 86BB, then six patterns from
     its bank 17 over the first ones);
  3. reads the stage palettes (patched ROM 0x2E400 + 32 * stage) and the
     sprite line-colour tables (0x2E600, 144 bytes) straight from the ROM,
     and makes the fire-coloured sprite copies;
  4. writes spec/msx2_stages.dat and spec/msx2_patches.txt (the patch's
     values at the data ranges listed in msx2_ranges.txt).
All three outputs are made from the user's files and are not distributed
(.gitignore).

msx2_stages.dat: 16 x 16K.  Banks 16-23, one per stage: VRAM 0000-37FF as the
load leaves it, the palette at 3800 (16 Next 9-bit colours), the line-colour
tables at 3820, and at 3900 a mask (a bit per VRAM byte, bit 0 first): set
where the load writes the byte.  Bytes it does not write keep whatever was
there (the patch's VRAM keeps them from earlier screens; so do the Next's
copies).  Banks 24-31: each stage's 64 sprite patterns in fire colours
(Next 4-bit, 128 bytes each; edge pixels 3, one in 4, deeper 5).  Bank 24
also holds, from 2000, the patch's title logo: its 4-bit bitmap (patched ROM
0x30000, 256 x 48, 128 bytes a line; the patch shows it at lines 16-63 of
its title screen) and at 3800 its palette (patched ROM 0x2E520).  Bank 25
holds, from 2000, our own drawings of Konami's enemies (art_page()).

Checked against openMSX captures of the patched cartridge at the end of each
stage load (2026-11-02): every byte the replay writes matches, apart from
characters Konami animates (F7, 78-7D), which it rewrites in play anyway.
One change of ours: stage 1's ground edge (character 43, bottom third) is
coloured as the patch colours it in stage 4 (68, not 6D: brown, not magenta).
"""
import os, sys, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, HERE)
import extract

IPS_NAME = 'Nemesis - Gradius ENHANCED V101.ips'
IPS_SHA256 = '46cda91d5bab061a580aae9aeed34e7ef253da9a128d3b92289e5a240a811b47'
ROM2_SHA256 = '1dee03fb9a42048c1ecd3d05a17a66e4f9cc9267716e4d479908bdc6d54eabbd'

def apply_ips(rom, ips):
    if ips[:5] != b'PATCH':
        raise SystemExit('not an IPS file')
    rom = bytearray(rom); i = 5
    while ips[i:i+3] != b'EOF':
        o = int.from_bytes(ips[i:i+3], 'big'); n = int.from_bytes(ips[i+3:i+5], 'big'); i += 5
        if n == 0:
            rl = int.from_bytes(ips[i:i+2], 'big'); data = bytes([ips[i+2]]) * rl; i += 3
        else:
            data = ips[i:i+n]; i += n
        if o + len(data) > len(rom):
            rom.extend(b'\xff' * (o + len(data) - len(rom)))
        rom[o:o+len(data)] = data
    return bytes(rom)

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

def stage_load(rom, s):
    """VRAM (Tracked) after the patched cartridge's 0:422A for stage s."""
    n = Patched(rom); v = Tracked(0x4000)
    b0 = lambda a: rom[a - 0x4000]
    # carga_la_fuente_de_la_fase (0:58BA in the patch): the status line's
    # colours (70) and characters, in the bottom third
    v[0x1008:0x1058] = bytes([0x70]) * 0x50
    v[0x1068:0x10A8] = bytes([0x70]) * 0x40
    v[0x3008:0x3058] = rom[0x1906:0x1956]
    a = 0x3068
    for i in range(0x58FD, 0x5906):
        idx = b0(i)
        if idx == 0:
            break
        v[a:a+8] = rom[0x196E + idx * 8:0x196E + idx * 8 + 8]; a += 8
    # the characters: Konami's records and mirrors
    n.load_records(v, 0x932D)
    n.load_records(v, n.u16(5, 0x92E3 + 2 * s))
    n.mirror(v, 0x92FB, s, False)
    n.mirror(v, 0x9313, s, True)
    # sprites: 86BB, then the patch's six patterns (bank 17, BA00) over the first
    n.decompress(v, 5, 0x86BB, 0x1800)
    v[0x1800:0x18C0] = rom[17 * 0x2000 + 0x1A00:17 * 0x2000 + 0x1AC0]
    # the stage's two sprite blocks (0:42AD + 6 * stage), stage 5's extra one
    t = 0x42AD + 6 * s
    for k in range(2):
        src = b0(t + 3*k) | b0(t + 3*k + 1) << 8; ch = b0(t + 3*k + 2)
        n.decompress(v, n.bank_for(src, extract.GFX), src, 0x1800 + ch * 8)
    if s == 5:
        n.decompress(v, n.bank_for(0x8FCB, extract.GFX), 0x8FCB, 0x1D00)
    return v

def next_palette(p):
    out = bytearray()
    for i in range(16):
        r = (p[2*i] >> 4) & 7; b = p[2*i] & 7; g = p[2*i+1] & 7
        hi = (r << 5) | (g << 2) | (b >> 1)
        if hi == 0xE3 and i:
            raise SystemExit('palette colour %d is the Layer 2 transparent colour' % i)
        out += bytes((hi, b & 1))
    out[0:2] = b'\0\0'
    return out

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

# Our own drawings (spec/nx_art.py: Konami's stage 1 enemies redrawn after the
# arcade game's sprites; made by local/tools/arcade/gen_art.py) in bank 25's
# second 8K (the Next's 8K page 51, ART_PAGE):
#   0000  the sprite drawings, 128 bytes each: Konami's patterns 30-46, then
#         the walkers' 52-63 (drawing n at (n - 1) * 128)
#   0E80  the character enemies' drawings (23), 128 bytes each
#   1A00  sprite palettes 2-10, entries 2-15 (28 bytes each, Next 9-bit)
#   1B00  the sprite drawings' palette bytes (drawing n at n - 1)
#   1B20  the character enemies (29): 6 bytes each: their four characters
#         (top left, top right, bottom left, bottom right: Konami's frame
#         table 5:91D1), palette byte, drawing number
#   1C00  128 bytes a stage: Konami pattern -> sprite drawing (64; 0 none),
#         then a byte per character enemy (1 on)
# A sprite's palette byte is palette * 16, + 1 where the next palette is its
# red twin, for the objects that leave a capsule (byte 14 set; Konami's
# colour 8).  The turrets that leave one Konami draws with red characters of
# their own (frames 09-0E): they are entries of their own, in red.
# A stage has an enemy's drawings where all that enemy's patterns or
# characters (ART_GROUPS: no enemy is drawn half ours, half Konami's) are
# stage 1's both in Konami's own load (nem.rom) and in the patch's (what the
# Next shows).  Build switches: NEM_ARC_SPR=0
# leaves Konami's sprite patterns (and the walkers) as they are, NEM_ARC_CHR=0
# the character enemies.
import nx_art
ART_CHR, ART_PAL, ART_APAL, ART_CHT, ART_MAP = 0x0E80, 0x1A00, 0x1B00, 0x1B20, 0x1C00
# the explosion, the shot, the pod, the robot, the jet, the walker (Konami's
# patterns); the fans, the saucers, the turrets on the ground and on the
# ceiling, the two capsules, the red turrets (nx_art.CHARS entries)
SPR_GROUPS = [range(30, 34), [34], range(35, 40), range(40, 44), range(44, 47), range(52, 64)]
CHR_GROUPS = [range(0, 4), range(4, 9), range(9, 15), range(15, 21), [21], [22], range(23, 29)]

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
    """patched: the patch's stage loads (build()'s data: 16K a stage)."""
    spr = bool(int(os.environ.get('NEM_ARC_SPR', '1')))
    chr_ = bool(int(os.environ.get('NEM_ARC_CHR', '1')))
    pg = bytearray(0x2000)
    pats = [(k,) + nx_art.SPRITES[k] for k in sorted(nx_art.SPRITES)] + \
           [(k,) + nx_art.WALKERS[k] for k in sorted(nx_art.WALKERS)]
    assert len(pats) <= 29 and len(nx_art.CHARS) == 29
    assert sorted(k for g in SPR_GROUPS for k in g) == [p[0] for p in pats]
    assert sorted(i for g in CHR_GROUPS for i in g) == list(range(29))
    num = {}
    for i, (k, pal, rows) in enumerate(pats):
        pg[i * 128:i * 128 + 128] = nibbles(rows); pg[ART_APAL + i] = pal; num[k] = i + 1
    for i, (c4, pal, rows) in enumerate(nx_art.CHARS):
        if isinstance(rows, int):
            d = rows; assert not isinstance(nx_art.CHARS[d][2], int)
        else:
            d = i; assert d < 23
            pg[ART_CHR + i * 128:ART_CHR + i * 128 + 128] = nibbles(rows)
        pg[ART_CHT + i * 6:ART_CHT + i * 6 + 6] = bytes(c4) + bytes([pal, d])
    assert ART_CHT + 29 * 6 <= ART_MAP and ART_APAL + 32 == ART_CHT and ART_PAL + 9 * 28 <= ART_APAL
    for p in range(2, 11):
        o = ART_PAL + (p - 2) * 28
        pg[o:o + 28] = bytes(b for e in nx_art.PALETTES[p][2:] for b in e)
    v1 = orig_load(rom, 1); p1 = patched[:0x4000]
    sp = lambda v, k: bytes(v[0x1800 + k * 32:0x1800 + k * 32 + 32])
    def ch(v, c4):
        return b''.join(bytes(v[o + t * 0x800 + c * 8:o + t * 0x800 + c * 8 + 8])
                        for c in c4 for t in range(3) for o in (0, 0x2000))
    report = []
    for s in range(1, 9):
        v = orig_load(rom, s); o = ART_MAP + (s - 1) * 128
        ps = patched[(s - 1) * 0x4000:s * 0x4000]
        same = lambda k: sp(v, k) == sp(v1, k) and sp(ps, k) == sp(p1, k)
        on = [k for g in SPR_GROUPS if spr and all(same(k) for k in g) for k in g]
        for k in on:
            pg[o + k] = num[k]
        chs = lambda i: ch(v, nx_art.CHARS[i][0]) == ch(v1, nx_art.CHARS[i][0]) and \
                        ch(ps, nx_art.CHARS[i][0]) == ch(p1, nx_art.CHARS[i][0])
        cs = [i for g in CHR_GROUPS if chr_ and all(chs(i) for i in g) for i in g]
        for i in cs:
            pg[o + 64 + i] = 1
        report.append('stage %d: patterns %s, character enemies %s' % (s, ','.join(map(str, sorted(on))) or '-',
                                                                    ','.join(map(str, cs)) or '-'))
    return bytes(pg), report

def build(rom, rom2, ranges):
    data = bytearray(); fires = bytearray()
    lines = rom2[0x2E600:0x2E690]
    for s in range(1, 9):
        v = stage_load(rom2, s)
        blk = bytearray(v[:0x3800])
        if s == 1:
            # The ground's lower edge (character 43 in the bottom third, its
            # top four lines): the patch colours it dark brown on magenta
            # (6D) in stage 1 but dark brown on the lighter brown (68) in
            # stage 4, where it is the same character.  Stage 1 as stage 4
            # (our choice, 3 November).
            e = 0x1000 + 0x43 * 8
            assert bytes(blk[e:e + 4]) == b'\x6d' * 4, bytes(blk[e:e + 8]).hex()
            blk[e:e + 4] = b'\x68' * 4
        blk += next_palette(rom2[0x2E400 + 32*s:0x2E420 + 32*s])
        blk += lines
        blk += bytes(0x3900 - len(blk))
        m = bytearray(0x700)
        for i in range(0x3800):
            if v.mask[i]:
                m[i >> 3] |= 1 << (i & 7)
        blk += m
        assert len(blk) == 0x4000
        data += blk
        f = bytearray()
        for n in range(64):
            f += fire(v[0x1800 + 32*n:0x1800 + 32*n + 32])
        if s == 1:
            # bank 24's second 8K: the patch's title logo (a 4-bit bitmap,
            # 256 x 48, MSX lines 16-63 of its title screen) and its palette
            f += bytes(0x2000 - len(f)) + rom2[0x30000:0x31800] + next_palette(rom2[0x2E520:0x2E540])
        fires += f + bytes(0x4000 - len(f))
    # bank 25's second 8K: our own drawings (art_page)
    art, report = art_page(rom, bytes(data))
    o = 0x4000 + 0x2000
    fires[o:o + len(art)] = art
    print('our drawings:\n  ' + '\n  '.join(report))
    # the patch's data values at our ranges (bank, first, last MSX address)
    lines_out = ['# generated by msx2_pack.py from nem.rom and the patched ROM: bank addr old new']
    for l in ranges:
        l = l.split('#')[0].split()
        if not l:
            continue
        bank, lo, hi = int(l[0]), int(l[1], 16), int(l[2], 16)
        base = {0: 0x4000, 1: 0x6000, 2: 0x8000, 3: 0xA000, 11: 0x8000}[bank]
        for a in range(lo, hi + 1):
            i = bank * 0x2000 + a - base
            if rom[i] != rom2[i]:
                lines_out.append('%d %04X %02X %02X' % (bank, a, rom[i], rom2[i]))
    return bytes(data + fires), '\n'.join(lines_out) + '\n'

def main():
    ips_path = os.path.join(ROOT, IPS_NAME)
    if not os.path.isfile(ips_path):
        print('no %s in %s: the Next build is made without the MSX2 graphics' % (IPS_NAME, ROOT))
        for f in ('msx2_stages.dat', 'msx2_patches.txt'):
            if os.path.exists(os.path.join(HERE, f)):
                os.remove(os.path.join(HERE, f))
        return
    ips = open(ips_path, 'rb').read()
    if hashlib.sha256(ips).hexdigest() != IPS_SHA256:
        sys.exit('%s is not the expected V1.01 patch' % IPS_NAME)
    rom = open(os.path.join(ROOT, 'nem.rom'), 'rb').read()
    rom2 = apply_ips(rom, ips)
    if hashlib.sha256(rom2).hexdigest() != ROM2_SHA256:
        sys.exit('the patched ROM is not the expected one')
    open(os.path.join(ROOT, 'nemmsx2.rom'), 'wb').write(rom2)
    ranges = open(os.path.join(HERE, 'msx2_ranges.txt')).read().split('\n')
    dat, patches = build(rom, rom2, ranges)
    open(os.path.join(HERE, 'msx2_stages.dat'), 'wb').write(dat)
    open(os.path.join(HERE, 'msx2_patches.txt'), 'w').write(patches)
    print('nemmsx2.rom, spec/msx2_stages.dat (%d bytes), spec/msx2_patches.txt (%d bytes)'
          % (len(dat), patches.count('\n') - 1))

if __name__ == '__main__':
    main()
