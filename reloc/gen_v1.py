"""Generate relocated Konami game code (MSX banks 0-3, 4, 5, 7, 8, 11) for the
Spectrum 128K layout, as one sjasmplus source.

Every item of the listing gets a label m<bank>_<addr>.  All address operands
become symbolic, so the assembler re-lays code that grows (RST 20h -> CALL).
Konami RAM E000-F0FF moves by RAM_DELTA.  Hardware touch points become calls
to shims defined by the platform layer (the layout simulator or the Spectrum
build), which must provide these symbols:
    dcompr, map_6000, map_8000, map_a000, bios_XXXX, bios_var_XXXX, hook_XXXX,
    vdp_* (port routines), far_page_<n> page numbers, set_page, cur_page
"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import re, sys, collections
from listing import parse

RAM_LO, RAM_HI = 0xE000, 0xF0FF
RAM_DELTA = -0x3100                     # E000 -> AF00

# Where each MSX bank lives on the Spectrum: (page or 'fixed', base address)
HOME = {0: ('fixed', 0x5B00), 1: ('A', 0xC000), 2: ('A', 0xE000), 3: ('C', 0xC000),
        4: ('B', 0xC000), 5: ('B', 0xE000), 11: ('E', 0xE000),
        7: ('D', 0xC000), 8: ('D', 0xE000)}
CODE_BANKS = (0, 1, 2, 3)
# Data moved out of a full Spectrum page into fixed RAM: (bank, start, length)
MOVED = [(1, 0x7EE6, 88)]
DATA_BANKS = (4, 5, 11, 7, 8)          # emitted as data (7 also holds code: handled as code)

# 16-bit immediates in ROM range that are plain numbers (reviewed by hand).
CONST_IMM = {0x55D1, 0x5742, 0x4C66, 0x703F, 0x76A0, 0x508D, 0xA8CB, 0xA908, 0x879E}
# Pointers into banks the Spectrum version does not hold (title screens etc.):
# left as numbers.
UNPLACED_IMM = {0x5B50, 0x5B59, 0x5B93, 0x5B98, 0x5C12, 0x5C1B, 0x5C24, 0x5C2D, 0x5C36,
                0x5C3F, 0x5C48, 0x5C51, 0x5C5A, 0x5C66}
# Sites whose 16-bit pointer refers to a bank other than the default (1,2,3) mapping.
SITE_BANK = {0x4A49: 7, 0x4035: 7,
             0x48CB: 5,                      # sprite engine table, banks 4/5/6 mapped
             0x46F2: 11, 0x4708: 11, 0x46C3: 11}

def default_bank(v):
    if v < 0x6000: return 0
    if v < 0x8000: return 1
    if v < 0xA000: return 2
    return 3

class Banks:
    def __init__(self, rom):
        self.items = {}; self.labels = {}; self.raw = {}; self.starts = {}
        for b in CODE_BANKS + (7,):
            it, lab, raw = parse(b, rom)
            self.items[b] = it; self.labels[b] = lab; self.raw[b] = raw
            self.starts[b] = sorted(i[0] for i in it)
        self.labelled = {b: set(v for v in self.labels[b].values() if v is not None) for b in self.labels}

    def sym(self, bank, v):
        """Symbolic reference to MSX address v in bank."""
        if bank not in self.starts:                    # pure data bank: fixed offset
            home, base = HOME[bank]
            org = {4: 0x6000, 5: 0x8000, 11: 0x8000, 8: 0xA000}[bank]
            return '0x%04X' % (base + v - org)
        st = self.starts[bank]
        import bisect
        i = bisect.bisect_right(st, v) - 1
        a = st[i]
        return 'm%d_%04X' % (bank, a) if a == v else 'm%d_%04X+%d' % (bank, a, v - a)

def ram(v):
    return '0x%04X' % (v + RAM_DELTA)

def gen(rom, out, identity=False):
    B = Banks(rom)
    global RAM_DELTA, HOME
    saved = (RAM_DELTA, dict(HOME))
    if identity:
        RAM_DELTA = 0
        for k in list(HOME): HOME[k] = ('fixed', {0: 0x4000, 1: 0x6000, 2: 0x8000, 3: 0xA000, 4: 0x6000, 5: 0x8000, 11: 0x8000, 7: 0x8000, 8: 0xA000}[k])
    lines = []; stubs = {}; report = collections.Counter(); notes = []; moved_global = []
    def far(bank, target_sym):
        page = HOME[bank][0]
        name = 'far_%s' % target_sym.replace('+', '_')
        stubs[name] = (page, target_sym)
        return name
    for b in CODE_BANKS + (7,):
        page, base = HOME[b]
        org = 0x4000 if b == 0 else {1: 0x6000, 2: 0x8000, 3: 0xA000, 7: 0x8000}[b]
        lines.append('\n; ===== MSX bank %d -> %s %04X =====' % (b, page, base))
        lines.append('    output "%s_bank%d.bin"' % (out[:-4], b) if identity else ('    page_%s' % page if page != 'fixed' else '    page_fixed'))
        lines.append('    org 0x%04X' % base)
        raw = B.raw[b]
        my_home = page
        moved_out = []
        for it in B.items[b]:
            a, n = it[0], it[1]
            if not identity and any(mb == b and ms <= a < ms + ml for mb, ms, ml in MOVED):
                moved_out.append(it); continue
            if not identity and b == 1 and a == 0x7FFE:
                # ld hl,0x8041 split across banks 1/2: emit whole, then continue in bank 2
                lines.append('m1_7FFE:')
                lines.append('    ld hl,' + B.sym(2, 0x8041))
                lines.append('    jp m2_8001'); continue
            lines.append('m%d_%04X:' % (b, a))
            byts = raw[a - org:a - org + n]
            if it[2] == 'defb':
                lines.append('    db ' + ','.join('0x%02X' % x for x in byts)); continue
            if it[2] == 'defw':
                words = [byts[i] | byts[i + 1] << 8 for i in range(0, n, 2)]
                ann = '->' in it[4]
                out_w = []
                for v in words:
                    if 0xE000 <= v <= 0xF0FF and ann:
                        out_w.append(ram(v)); report['dw ram'] += 1
                    elif 0x4000 <= v < 0xC000 and (ann or v in B.labelled.get(default_bank(v), ())):
                        out_w.append(B.sym(default_bank(v), v)); report['dw ptr'] += 1
                    else:
                        out_w.append('0x%04X' % v)
                lines.append('    dw ' + ','.join(out_w)); continue
            # code
            text, kind = it[3].lower(), it[5]
            op = byts[0]
            if b == 7:                      # sound driver: relocate within its own banks
                if kind is not None:
                    v = byts[-2] | byts[-1] << 8
                    if 0x8000 <= v < 0xC000:
                        tb = 7 if v < 0xA000 else 8
                        s = B.sym(7, v) if tb == 7 else '0x%04X' % (HOME[8][1] + v - 0xA000)
                    elif RAM_LO <= v <= RAM_HI: s = ram(v)
                    elif v < 0x4000 and kind in ('jp16', 'call16'): s = ('0x%04X' % v) if identity else 'bios_%04X' % v
                    else: s = '0x%04X' % v
                    lines.append('    db ' + ','.join('0x%02X' % x for x in byts[:-2]))
                    lines.append('    dw ' + s); continue
            if op == 0xE7 and not identity:                         # RST 20h
                lines.append('    call dcompr'); report['rst20'] += 1; continue
            if op in (0x10, 0x18, 0x20, 0x28, 0x30, 0x38):         # relative jumps
                d = byts[1] - 256 if byts[1] > 127 else byts[1]
                t = a + 2 + d
                mn = {0x10: 'djnz', 0x18: 'jr', 0x20: 'jr nz,', 0x28: 'jr z,', 0x30: 'jr nc,', 0x38: 'jr c,'}[op]
                lines.append('    %s %s' % (mn if mn.endswith(',') else mn + ' ', B.sym(b, t)) if not mn.endswith(',')
                             else '    %s%s' % (mn, B.sym(b, t)))
                continue
            if kind is None:
                lines.append('    db ' + ','.join('0x%02X' % x for x in byts)); continue
            v = byts[-2] | byts[-1] << 8
            pre = byts[:-2]
            if kind in ('jp16', 'call16'):
                if v < 0x4000:
                    s = ('0x%04X' % v) if identity else 'bios_%04X' % v; report['bios'] += 1
                else:
                    tb = SITE_BANK.get(a, default_bank(v))
                    s = B.sym(tb, v) if tb in B.starts else '0x%04X' % v
                    th = HOME[tb][0]
                    if th != 'fixed' and th != my_home:
                        s = far(tb, s); report['far'] += 1
                lines.append('    db ' + ','.join('0x%02X' % x for x in pre)); lines.append('    dw ' + s); continue
            if kind == 'abs16':
                if v in (0x6000, 0x8000, 0xA000) and op == 0x32 and not identity:
                    lines.append('    call map_%04x' % v); report['mapper'] += 1; continue
                if RAM_LO <= v <= RAM_HI: s = ram(v); report['ram'] += 1
                elif v < 0x4000: s = ('0x%04X' % v) if identity else 'bios_var_%04X' % v; report['biosvar'] += 1
                elif v >= 0xF100: s = ('0x%04X' % v) if identity else 'hook_%04X' % v; report['hook'] += 1
                else:
                    tb = SITE_BANK.get(a, default_bank(v)); s = B.sym(tb, v); report['abs rom'] += 1
                lines.append('    db ' + ','.join('0x%02X' % x for x in pre)); lines.append('    dw ' + s); continue
            if kind == 'imm16':
                if RAM_LO <= v <= RAM_HI: s = ram(v); report['imm ram'] += 1
                elif 0x4000 <= v < 0xC000 and a not in CONST_IMM and a not in UNPLACED_IMM:
                    tb = SITE_BANK.get(a, default_bank(v))
                    s = B.sym(tb, v) if (tb in B.starts or tb in HOME) else '0x%04X' % v
                    report['imm ptr'] += 1
                else:
                    s = '0x%04X' % v; report['imm const'] += 1
                lines.append('    db ' + ','.join('0x%02X' % x for x in pre)); lines.append('    dw ' + s); continue
            raise ValueError('unhandled %04X %s' % (a, text))
        if moved_out:
            moved_global.extend((b, it) for it in moved_out)
    # Data banks: raw (their internal pointers are not used through absolute
    # addresses in stage 1; revisit for other stages).
    rawdata = {}
    for b in (4, 5, 11, 8):
        rawdata[b] = rom[b * 8192:(b + 1) * 8192]
    if moved_global:
        lines.append('\n; ===== data moved to fixed RAM =====')
        lines.append('    page_fixed2')
        for b, it in moved_global:
            org = {1: 0x6000, 2: 0x8000, 3: 0xA000}[b]
            byts = B.raw[b][it[0] - org:it[0] - org + it[1]]
            lines.append('m%d_%04X:' % (b, it[0]))
            if it[2] == 'defw':
                lines.append('    dw ' + ','.join('0x%04X' % (byts[i] | byts[i+1] << 8) for i in range(0, it[1], 2)))
            else:
                lines.append('    db ' + ','.join('0x%02X' % x for x in byts))
    # Data banks placed raw.
    if not identity:
        for b, off in ((4, 0), (5, 0), (11, 0), (8, 0)):
            page, base = HOME[b]
            lines.append('\n; ===== MSX bank %d (data) -> %s %04X =====' % (b, page, base))
            lines.append('    page_%s' % page)
            lines.append('    org 0x%04X' % base)
            lines.append('    incbin "ROMFILE",%d,8192' % (b * 8192))
    # Far-call stubs (fixed RAM).
    stub_lines = ['\n; ===== far-call stubs (fixed RAM) =====']
    for name, (page, target) in sorted(stubs.items()):
        stub_lines += ['%s:' % name,
                       '    push hl', '    ld hl,(cur_page)', '    ex (sp),hl',
                       '    push af', '    ld a,PAGE_%s' % page, '    call set_page', '    pop af',
                       '    call %s' % target,
                       '    ex (sp),hl', '    push af', '    ld a,l', '    call set_page', '    pop af',
                       '    pop hl', '    ret']
    RAM_DELTA, HOME = saved[0], saved[1]
    open(out, 'w').write('\n'.join(lines) + '\n')
    open(out.replace('.asm', '_stubs.asm'), 'w').write('\n'.join(stub_lines) + '\n')
    return report, stubs, rawdata

if __name__ == '__main__':
    rom = open(NEM_ROOT + '/nem.rom', 'rb').read()
    rep, stubs, _ = gen(rom, NEM_ROOT + '/reloc/konami_reloc.asm')
    for k, v in sorted(rep.items()): print(k, v)
    print('far stubs:', len(stubs))
