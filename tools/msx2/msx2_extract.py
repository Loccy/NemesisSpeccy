"""Remakes the Next build's graphics files (spec/nxgfx/: the stages, the logo,
the data bytes) from the MSX2 patch "Nemesis - Gradius ENHANCED" V1.01, as
they were first made (3 November 2026).  Not part of the build: the files
are ours now and changed since (see nx_pack.py), so a remake starts them
over; compare before keeping it.

  msx2_extract.py IPS OUTDIR

It applies the IPS to nem.rom (both checked by SHA-256) and replays the
patched cartridge's stage graphics load (0:422A) for each stage, statically,
with extract.py's replay of Konami's loader (the patch keeps Konami's loader
and data format; it changes the data, the status-line font routine at 0:58BA
and the sprite load, which it sends through its own code: Konami's block at
86BB, then six patterns from its bank 17 over the first ones); reads the
stage palettes (patched ROM 0x2E400 + 32 * stage), the sprite line-colour
tables (0x2E600, 144 bytes), the title logo (0x30000, its palette 0x2E520)
straight from the ROM; and lists the patch's values in the data ranges of
spec/msx2_ranges.txt.  Checked against openMSX captures of the patched
cartridge at the end of each stage load (2026-11-02): every byte the replay
writes matches, apart from characters Konami animates (F7, 78-7D), which it
rewrites in play anyway.  Our change then: stage 1's ground edge."""
import os, sys, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.normpath(os.path.join(HERE, '..', '..', 'spec'))
ROOT = os.path.normpath(os.path.join(SPEC, '..'))
sys.path.insert(0, SPEC)
import extract
from nx_pack import Tracked, Patched

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

def extract_all(rom, rom2, ranges):
    """-> {file name: bytes} for spec/nxgfx."""
    out = {}
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
        out['stage%d.bin' % s] = bytes(blk)
    out['logo.bin'] = rom2[0x30000:0x31800] + next_palette(rom2[0x2E520:0x2E540])
    lines_out = ['# the data bytes the Next build changes in Konami\'s ranges: bank addr old new']
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
    out['patches.txt'] = ('\n'.join(lines_out) + '\n').encode()
    return out

def main():
    ips = open(sys.argv[1], 'rb').read()
    if hashlib.sha256(ips).hexdigest() != IPS_SHA256:
        sys.exit('not the expected V1.01 patch')
    rom = open(os.path.join(ROOT, 'nem.rom'), 'rb').read()
    rom2 = apply_ips(rom, ips)
    if hashlib.sha256(rom2).hexdigest() != ROM2_SHA256:
        sys.exit('the patched ROM is not the expected one')
    ranges = open(os.path.join(HERE, 'msx2_ranges.txt')).read().split('\n')
    os.makedirs(sys.argv[2], exist_ok=True)
    for name, b in extract_all(rom, rom2, ranges).items():
        open(os.path.join(sys.argv[2], name), 'wb').write(b)
        print(name, len(b))

if __name__ == '__main__':
    main()
