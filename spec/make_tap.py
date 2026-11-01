"""Build nemesis.tap from nemesis.sna for a standard 128K Spectrum.

Tape: a BASIC loader (BORDER/PAPER/INK 0, CLS, CLEAR, LOAD ""CODE to 16384,
RANDOMIZE USR 16384), a
small machine-code loader that sits in screen memory, then headerless blocks.
The loader pages each RAM bank in at C000 (with the 48K ROM, bit 4 of 7FFD)
and reads its block with the ROM's LD-BYTES.  It does LD-BYTES's set-up
itself, pushing its own return address rather than SA/LD-RET's (which would
enable interrupts and check BREAK while the system variables are being
overwritten), and joins the ROM at 0562, the instruction DivMMC-type
interfaces trap to load a .tap file from their card (entering any later, as
before 0.94a, bypassed the trap and the loader waited for a real tape).  In
case such an interface returns through SA/LD-RET anyway, interrupts are in
mode 2 with a table at BD00 (I = BD) whose handler is a bare RET, so one can
do no harm and leaves interrupts off; the table is rebuilt for every block
(the loader clears bank 2's area on the way) and cleared before the game
starts.
Memory the game expects to be zero is cleared first.  The last block is
5B00 onwards, then the loader jumps to plat_boot.
"""
import functools, os, re, subprocess, sys
from skoolkit.snapshot import Snapshot
HERE = os.path.dirname(os.path.abspath(__file__))
ZX0 = os.environ.get('ZX0', 'zx0')     # https://github.com/einar-saukas/ZX0 (gcc -O2 -o zx0 zx0.c optimize.c compress.c memory.c); on the PATH or named by ZX0
TOK = {'CLEAR': 0xFD, 'VAL': 0xB0, 'LOAD': 0xEF, 'CODE': 0xAF, 'RANDOMIZE': 0xF9, 'USR': 0xC0,
       'BORDER': 0xE7, 'PAPER': 0xDA, 'INK': 0xD9, 'CLS': 0xFB, 'NOT': 0xC3, 'PI': 0xA7}

def block(data, flag):
    body = bytes([flag]) + data
    return (len(body) + 1).to_bytes(2, 'little') + body + bytes([functools.reduce(lambda a, b: a ^ b, body, 0)])

def header(name, typ, length, p1, p2):
    h = bytes([typ]) + name.encode()[:10].ljust(10) + length.to_bytes(2, 'little') + p1.to_bytes(2, 'little') + p2.to_bytes(2, 'little')
    return block(h, 0)

def basic(line):
    data = line + b'\r'
    return (10).to_bytes(2, 'big') + len(data).to_bytes(2, 'little') + data

def main(sna='nemesis.sna', tap='nemesis.tap', name='NEMESIS'):
    syms = {}
    for l in open(os.path.join(HERE, sna.replace('.sna', '.sym'))):
        m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
        if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
    B = Snapshot.get(os.path.join(HERE, sna)).memory.banks
    loads = []; zeros = []
    def plan(bank, base, lo, hi):              # bank's bytes lo..hi-1 at CPU address base+offset
        d = B[bank]; nz = [i for i in range(lo, hi) if d[i]]
        start = nz[0] if nz else lo; end = nz[-1] + 1 if nz else lo
        zeros.append((bank, base + lo, hi - lo))  # clear the whole region first
        if end > start: loads.append((bank, base + start, bytes(d[start:end])))
    for bank in (0, 1, 3, 4, 6, 7):
        plan(bank, 0xC000, 0, 0x4000)
    plan(2, 0x8000, 0, 0x4000)
    plan(5, 0x4000, 0x1B00, 0x4000)            # 5B00-7FFF (the screen is cleared by the game)
    if os.environ.get('NEM_TAP_RAW') != '1':  # bank 7's own block last: its area at DB00 up is bank 5's buffer
        loads.sort(key=lambda l: l[0] == 7)
    # the loader (in screen memory: 4000 up, stack below 5800)
    asm = ['    device zxspectrum128', '    org 0x4000', 'start:', '    di', '    ld sp,0x5800',
           '    ld a,0xbd', '    ld i,a', '    im 2']             # see the docstring: interrupts harmless
    for bank, addr, n in zeros:
        if addr >= 0x5B00 and addr < 0x8000: continue      # cleared just before its block is loaded
        asm += ['    ld a,0x%02X' % (0x10 | (bank if addr >= 0xC000 else 0)), '    call page',
                '    ld hl,0x%04X' % addr, '    ld bc,0x%04X' % n, '    call zero']
    # The loading screen: into bank 7 at C000 (the 128K's second screen) once
    # the banks are cleared, then shown (bit 3 of 7FFD) while the rest
    # loads (shown from the start, so it builds up as it loads); the loader
    # itself sits in the first screen, out of sight.
    scr = open(os.path.join(HERE, 'tape', 'loading.scr'), 'rb').read() if os.path.exists(os.path.join(HERE, 'tape', 'loading.scr')) else None
    show = 0
    if scr:
        assert len(scr) == 6912
        asm += ['    ld a,0x1F', '    call page', '    ld ix,0xC000', '    ld de,6912', '    call load']
        show = 0x08
    # The blocks, ZX0-compressed (tape/dzx0_standard.asm unpacks them; the
    # compressor is Einar Saukas's zx0, BSD licence, tape/ZX0_LICENSE): each is
    # loaded into memory that is free at that point, then unpacked into place.
    #   paged banks (C000): loaded at 8000 (bank 2's area, cleared afterwards)
    #   bank 2 (8000 up):   loaded at 5B00 (bank 5's area, cleared afterwards)
    #   bank 5 (5B00 up):   loaded into bank 7 at DB00 (the tile set's area and
    #                       above, cleared afterwards, before bank 7's own small
    #                       block), unpacked with bank 7 paged in
    raw = os.environ.get('NEM_TAP_RAW') == '1'
    blocks = []
    def zx0(data):
        tmp = os.path.join(HERE, 'tape', 'block.bin')
        open(tmp, 'wb').write(data)
        if os.path.exists(tmp + '.zx0'): os.remove(tmp + '.zx0')
        subprocess.run([ZX0, '-f', tmp], check=True, capture_output=True)
        out = open(tmp + '.zx0', 'rb').read(); os.remove(tmp); os.remove(tmp + '.zx0')
        return out
    done_paged = False
    assert all(b != 2 or a + len(d) <= 0xBD00 for b, a, d in loads)    # bank 2's data clear of the interrupt table
    for bank, addr, data in loads:
        pg = '0x%02X' % (0x10 | show | (bank if addr >= 0xC000 else 0))
        if addr < 0xC000 and not done_paged and not raw:
            asm += ['    ld hl,0x8000', '    ld bc,0x4000', '    call zero']    # the paged banks' buffer
            done_paged = True
        if addr == 0x5B00:
            asm += ['    ld hl,0x5B00', '    ld bc,0x2500', '    call zero']
        if raw or len(data) < 256 or bank == 7:     # bank 7's block comes last: its buffer at 8000 would be bank 2's data by then
            asm += ['    ld a,%s' % pg, '    call page',
                    '    ld ix,0x%04X' % addr, '    ld de,0x%04X' % len(data), '    call load']
            blocks.append(data); continue
        c = zx0(data)
        if addr >= 0xC000: buf, bpg, room = 0x8000, pg, 0x4000
        elif addr >= 0x8000: buf, bpg, room = 0x5B00, pg, 0x8000 - 0x5B00
        else: buf, bpg, room = 0xDB00, '0x%02X' % (0x10 | show | 7), 0x10000 - 0xDB00
        assert len(c) <= room, (bank, len(c), room)
        assert buf != 0x8000 or buf + len(c) <= 0xBD00, (bank, len(c))     # clear of the interrupt table
        asm += ['    ld a,%s' % bpg, '    call page',
                '    ld ix,0x%04X' % buf, '    ld de,0x%04X' % len(c), '    call load',
                '    ld hl,0x%04X' % buf, '    ld de,0x%04X' % addr, '    call dzx0_standard']
        if buf == 0xDB00:
            asm += ['    ld hl,0xDB00', '    ld bc,0x%04X' % len(c), '    call zero']
        if buf == 0x5B00:
            pass                                    # cleared before bank 5's block
        blocks.append(c)
    asm += ['    di', '    ld hl,0xBD00', '    ld bc,0x01BF', '    call zero',     # the interrupt table: Konami's RAM, zero
            '    ld a,0x10', '    call page', '    jp 0x%04X' % syms['plat_boot'],
            'page:', '    ld bc,0x7ffd', '    out (c),a', '    ret',
            'zero:', '    ld (hl),0', '    ld d,h', '    ld e,l', '    inc de', '    dec bc', '    ldir', '    ret',
            'load:', '    push de', '    ld hl,0xBD00', '    ld de,0xBD01', '    ld bc,0x0100',
            '    ld (hl),0xBE', '    ldir', '    ld a,0xC9', '    ld (0xBEBE),a', '    pop de',   # IM 2 table -> BEBE: ret
            '    ld a,0xff', '    scf', '    inc d', '    ex af,af\'', '    dec d', '    di',
            '    ld a,0x0f', '    out (0xfe),a', '    ld hl,.ret', '    push hl', '    jp 0x0562',
            '.ret:', '    di', '    jr nc,failed', '    ret',
            'failed:', '    ld a,2', '    out (0xfe),a', '    jr failed',
            '    include "dzx0_standard.asm"',
            'end:', '    savebin "tape/loader.bin",start,end-start']
    open(os.path.join(HERE, 'tape', 'loader.asm'), 'w').write('\n'.join(asm) + '\n')
    r = subprocess.run(['sjasmplus', '--nologo', '--msg=war', 'tape/loader.asm'], cwd=HERE, capture_output=True, text=True)
    if r.returncode: sys.exit(r.stdout + r.stderr)
    loader = open(os.path.join(HERE, 'tape', 'loader.bin'), 'rb').read()
    assert len(loader) < 0x1000
    # BORDER 0: PAPER 0: INK 0: CLS first (0 as NOT PI), so the machine-code
    # loader's bytes in screen memory are black on black
    zero = bytes([TOK['NOT'], TOK['PI']])
    line = (bytes([TOK['BORDER']]) + zero + b':' + bytes([TOK['PAPER']]) + zero + b':' +
            bytes([TOK['INK']]) + zero + b':' + bytes([TOK['CLS']]) + b':' +
            bytes([TOK['CLEAR']]) + b' ' + bytes([TOK['VAL']]) + b'"24575":' + bytes([TOK['LOAD']]) + b'""' +
            bytes([TOK['CODE']]) + b':' + bytes([TOK['RANDOMIZE']]) + b' ' + bytes([TOK['USR']]) + b' ' +
            bytes([TOK['VAL']]) + b'"16384"')
    prog = basic(line)
    tape = header(name, 0, len(prog), 10, len(prog)) + block(prog, 0xFF)
    tape += header('loader', 3, len(loader), 0x4000, 0x8000) + block(loader, 0xFF)
    if scr:
        tape += block(scr, 0xFF)
    for data in blocks:
        tape += block(data, 0xFF)
    open(os.path.join(HERE, tap), 'wb').write(tape)
    print('%s: %d bytes, %d data blocks: %s' % (tap, len(tape), len(loads),
          ', '.join('bank %d %04X+%d (%d on tape)' % (b, a, len(d), len(c)) for (b, a, d), c in zip(loads, blocks))))

if __name__ == '__main__':
    main(*sys.argv[1:])
