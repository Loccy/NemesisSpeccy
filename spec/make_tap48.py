"""Build nemesis48.tap, the 48K multiload, from each stage's image
(nemesis48.sna for stage 1, nemesis48_sN.sna for the others).

Tape: a BASIC loader (BORDER/PAPER/INK 0, CLS, CLEAR, LOAD ""SCREEN$,
POKE 23739,111 so that the ROM prints no "Bytes:" over the picture, LOAD
""CODE to 61440, RANDOMIZE USR 61440), the loading screen (tape/loading.scr,
the 128K's), a small machine-code loader at F000, then headerless blocks:
Konami's RAM area AF00-BFFF from stage 1's image (flag 0x30: with the
multiload's loader at BF01, z48_fixed.asm), the shared core (5B00-AEFF, flag
0x40; C000 up to the stage blocks, flag 0x41), then each stage's block (flag
0x10 + stage).  (Without the shared layout: each stage's 5B00-AEFF, flag
0x10 + stage, and C000-FFFF, flag 0x20 + stage.)  With the shared layout
every block is ZX0-packed (as make_tap.py's): the core first, loaded in place
(ending 3 bytes into AF00-AF02, ZX0's delta), then Konami's RAM block and the
rest of the core (C000 up), each loaded at C400 and unpacked into place by the
first loader's own dzx0_standard; each stage's block, padded at the front to
the longest, holds its last 3 bytes, the packed data's start, the padding and
the packed data ending at FFFF, which the multiload's loader (z48_fixed.asm)
unpacks in place with the core's dzx0_standard (about 0.6 seconds), the 3
bytes then put at FFFD; the length and address are written into Konami's RAM
block (z48_lx, z48_ll, z48_lx2).  The first loader reads
the first blocks with the ROM's LD-BYTES (joined at 0562, as make_tap.py
does, so that DivMMC-type interfaces can trap it), and jumps to the
multiload's loader for stage 1, which starts the game (z48_enter, A = 0:
plat_boot; the game clears the picture).  The loader, its stack (below
F000) and its interrupt table (F200, handler F3F3) sit where stage 1's
block loads last, out of the picture; interrupts are in mode 2 meanwhile,
with a handler that is a bare RET, so that an interface returning through
SA/LD-RET with interrupts on cannot run the ROM's handler over the system
variables being loaded.  Before the jump to BF01 the table is the core's
own (AD00, z48_fixed.asm), as stage 1's block loads over F000 up.  
"""
import os, re, subprocess, sys
from make_tap import block, header, basic, TOK, ZX0
HERE = os.path.dirname(os.path.abspath(__file__))

def image(sna):
    img = open(os.path.join(HERE, sna), 'rb').read()[27:]
    assert len(img) == 0xC000
    return img

def ov48(sna):
    for l in open(os.path.join(HERE, sna.replace('.sna', '.sym'))):
        if l.startswith('z48_hdr:'): return int(l.split('0x')[1], 16) & 0xFFFF
    return None

def zx0(data):
    """ZX0-packed data, and its delta (for unpacking in place); Einar Saukas's zx0 (make_tap.py)."""
    # zx0 takes about two seconds a block, so its answers are kept by the
    # data's hash (zx0cache48/, not in the repository): an unchanged block
    # is not packed again
    import hashlib
    cd = os.path.join(HERE, 'zx0cache48'); os.makedirs(cd, exist_ok=True)
    cf = os.path.join(cd, hashlib.md5(data).hexdigest())
    if os.path.exists(cf):
        c = open(cf, 'rb').read()
        return c[2:], c[0] | c[1] << 8
    out, delta = _zx0(data)
    open(cf, 'wb').write(bytes([delta & 0xFF, delta >> 8]) + out)
    return out, delta

def _zx0(data):
    tmp = os.path.join(HERE, 'tape', 'block48.bin')
    open(tmp, 'wb').write(data)
    if os.path.exists(tmp + '.zx0'): os.remove(tmp + '.zx0')
    r = subprocess.run([ZX0, '-f', tmp], check=True, capture_output=True, text=True)
    out = open(tmp + '.zx0', 'rb').read(); os.remove(tmp); os.remove(tmp + '.zx0')
    return out, int(re.search(r'delta (\d+)', r.stdout).group(1))

def main(tap='nemesis48.tap', name='NEMESIS48', *snas):
    snas = snas or ('nemesis48.sna',)
    imgs = [image(x) for x in snas]
    kram = imgs[0][0xAF00 - 0x4000:0xC000 - 0x4000]
    ov = ov48(snas[0])          # the shared layout: the core loaded once, then a block a stage
    if ov:
        for x, img in zip(snas, imgs):
            assert ov48(x) == ov and img[0x1B00:0xAF00 - 0x4000] == imgs[0][0x1B00:0xAF00 - 0x4000] \
                and img[0x8000:ov - 0x4000] == imgs[0][0x8000:ov - 0x4000], '%s: not the same core' % x
    if ov:
        # Packed (ZX0, as make_tap.py; 14 November): the core, Konami's RAM block and each
        # stage's block.  The first loader unpacks the first three (its own copy of
        # dzx0_standard); the multiload's loader (z48_fixed.asm) the stages', with the core's.
        syms = {}
        for l in open(os.path.join(HERE, snas[0].replace('.sna', '.sym'))):
            m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
            if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
        core = imgs[0][0x1B00:0xAF00 - 0x4000]
        core2 = imgs[0][0x8000:ov - 0x4000]
        pc, dc = zx0(core)
        assert dc <= 3, dc
        core_x = 0xAF00 + 3 - len(pc)        # in place: the packed core ends 3 past AEFF (into AF00-AF02,
                                              # Konami's RAM block, loaded after it)
        # every stage's block the same length on tape: its last 3 bytes, the packed data's
        # start (2 bytes), padding, the packed data (ending at FFFF; unpacked in place to
        # OV48-FFFC, ZX0's delta at most 3)
        packs = []
        for img in imgs:
            blk = img[ov - 0x4000:]
            p_, d_ = zx0(blk[:-3])
            assert d_ <= 3, d_
            packs.append((blk[-3:], p_))
        L = max(len(p_) for _, p_ in packs) + 5
        X = 0x10000 - L
        assert X >= ov
        stages = [tail + (0x10000 - len(p_)).to_bytes(2, 'little') + bytes(L - 5 - len(p_)) + p_ for tail, p_ in packs]
        kram = bytearray(kram)
        for sym, v in (('z48_lx', X), ('z48_ll', L), ('z48_lx2', X)):
            kram[syms[sym] - 0xAF00:syms[sym] - 0xAF00 + 2] = v.to_bytes(2, 'little')
        kram = bytes(kram)
        pk, dk = zx0(kram)
        p2, d2 = zx0(core2) if core2 else (b'', 0)
        assert 0xC400 + len(pk) <= 0xF000 and 0xC400 + len(p2) <= 0xF000
        def ld(lab, flag, ix, n):
            return ['%s:' % lab, '    ld ix,0x%04X' % ix, '    ld de,0x%04X' % n,
                    '    ld a,0x%02X' % flag, '    scf', '    inc d', "    ex af,af'", '    dec d', '    di',
                    '    ld a,0x0f', '    out (0xfe),a', '    call 0x0562', '    di', '    jr nc,%s' % lab]
        def unz(src, dst):
            return ['    ld hl,0x%04X' % src, '    ld de,0x%04X' % dst, '    call dzx0_standard']
        asm = ['    device zxspectrum48', '    org 0xF000', 'start:', '    di', '    ld sp,0xF000',
               '    ld hl,0xF200', '    ld de,0xF201', '    ld bc,0x0100', '    ld (hl),0xF3', '    ldir',
               '    ld a,0xC9', '    ld (0xF3F3),a', '    ld a,0xF2', '    ld i,a', '    im 2']
        asm += ld('.core', 0x40, core_x, len(pc)) + unz(core_x, 0x5B00)
        asm += ld('.kram', 0x30, 0xC400, len(pk)) + unz(0xC400, 0xAF00)
        if core2: asm += ld('.core2', 0x41, 0xC400, len(p2)) + unz(0xC400, 0xC000)
        asm += ['    ld a,0xAD', '    ld i,a',        # the core's own table (z48_fixed.asm): stage 1's block loads over F000 up
                '    ld a,1', '    ld c,0', '    jp 0xBF01',
                '    include "dzx0_standard.asm"',
                'end:', '    savebin "tape/loader48.bin",start,end-start']
    else:
        asm = ['    device zxspectrum48', '    org 0xF000', 'start:', '    di', '    ld sp,0xF000',
               '    ld hl,0xF200', '    ld de,0xF201', '    ld bc,0x0100', '    ld (hl),0xF3', '    ldir',
               '    ld a,0xC9', '    ld (0xF3F3),a', '    ld a,0xF2', '    ld i,a', '    im 2',
               '.again:', '    ld ix,0xAF00', '    ld de,0x%04X' % len(kram),
               '    ld a,0x30', '    scf', '    inc d', "    ex af,af'", '    dec d', '    di',
               '    ld a,0x0f', '    out (0xfe),a', '    call 0x0562', '    di', '    jr nc,.again',
               '    ld a,1', '    ld c,0', '    jp 0xBF01',
               'end:', '    savebin "tape/loader48.bin",start,end-start']
    open(os.path.join(HERE, 'tape', 'loader48.asm'), 'w').write('\n'.join(asm) + '\n')
    r = subprocess.run(['sjasmplus', '--nologo', '--msg=war', 'tape/loader48.asm'], cwd=HERE, capture_output=True, text=True)
    if r.returncode: sys.exit(r.stdout + r.stderr)
    loader = open(os.path.join(HERE, 'tape', 'loader48.bin'), 'rb').read()
    assert len(loader) < 0x200                       # (clear of the table at F200)
    # The loading screen (the 128K's, tape/loading.scr): loaded by LOAD ""SCREEN$ before the
    # loader, which sits at F000 up (its table at F100), out of the picture
    sp = os.path.join(HERE, 'tape', 'loading.scr')
    scr = open(sp, 'rb').read() if os.path.exists(sp) else None
    if scr: assert len(scr) == 6912
    zero = bytes([TOK['NOT'], TOK['PI']])
    line = (bytes([TOK['BORDER']]) + zero + b':' + bytes([TOK['PAPER']]) + zero + b':' +
            bytes([TOK['INK']]) + zero + b':' + bytes([TOK['CLS']]) + b':' +
            bytes([TOK['CLEAR']]) + b' ' + bytes([TOK['VAL']]) + b'"24575":' +
            (bytes([TOK['LOAD']]) + b'""' + bytes([0xAA]) + b':' +       # SCREEN$, then POKE 23739,111: the ROM's
             bytes([0xF4]) + bytes([TOK['VAL']]) + b'"23739",' + bytes([TOK['VAL']]) + b'"111":' if scr else b'') +   # "Bytes:" not over the picture
            bytes([TOK['LOAD']]) + b'""' +
            bytes([TOK['CODE']]) + b':' + bytes([TOK['RANDOMIZE']]) + b' ' + bytes([TOK['USR']]) + b' ' +
            bytes([TOK['VAL']]) + b'"61440"')
    prog = basic(line)
    t = header(name, 0, len(prog), 10, len(prog)) + block(prog, 0xFF)
    if scr: t += header('screen', 3, 6912, 0x4000, 0x8000) + block(scr, 0xFF)
    t += header('loader', 3, len(loader), 0xF000, 0x8000) + block(loader, 0xFF)
    if ov:
        t += block(pc, 0x40) + block(pk, 0x30)
        if core2: t += block(p2, 0x41)
        for n, st in enumerate(stages, 1):
            t += block(st, 0x10 + n)
        print('packed: core %d, Konami RAM %d, core 2 %d, stages %s (each %d on tape)' % (len(pc), len(pk), len(p2), [len(p_) for _, p_ in packs], L))
    else:
      t += block(kram, 0x30)
      for n, img in enumerate(imgs, 1):
        t += block(img[0x1B00:0xAF00 - 0x4000], 0x10 + n) + block(img[0xC000 - 0x4000:], 0x20 + n)
    open(os.path.join(HERE, tap), 'wb').write(t)
    print('%s: %d bytes (stages 1-%d)' % (tap, len(t), len(imgs)))

if __name__ == '__main__':
    main(*sys.argv[1:])
