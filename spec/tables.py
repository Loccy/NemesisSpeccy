"""Generate tables.asm: colour conversion, keyboard map, screen address tables."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys
sys.path.insert(0, NEM_ROOT + '/w31/tools')
from convert import PALETTES, dist2
from extract import TMS

SH = 8          # D = squared RGB distance >> 8: products and sums stay within 16 bits

def tables():
    out = []
    # D[br][m][z], 16-bit, laid out as cv_dist + br*256 + m*16 + z*2
    out.append('    align 256')
    out.append('cv_dist:          ; squared distance MSX colour m -> ZX colour z (bright br), >> %d' % SH)
    for br in (0, 1):
        for m in range(16):
            ds = [dist2(TMS[m], PALETTES[br][z]) >> SH for z in range(8)]
            out.append('    dw ' + ','.join(str(d) for d in ds))
    out.append('lsb_index:        ; index of the lowest set bit')
    v = [0] + [(x & -x).bit_length() - 1 for x in range(1, 256)]
    for i in range(0, 256, 16):
        out.append('    db ' + ','.join(str(x) for x in v[i:i + 16]))
    # NEAR[br][m] : cv_near + br*16 + m
    out.append('cv_near:          ; nearest ZX colour (0-7) to MSX colour m at bright br')
    for br in (0, 1):
        D = [[dist2(TMS[m], PALETTES[br][z]) >> SH for z in range(8)] for m in range(16)]
        out.append('    db ' + ','.join(str(min(range(8), key=lambda z: (D[m][z], z))) for m in range(16)))
    # Sprite colour: TMS colour -> ZX ink | bright<<6 (nearest over both brights)
    out.append('spr_ink:          ; MSX sprite colour -> ZX ink + bright')
    v = []
    for m in range(16):
        br, z = min(((br, z) for br in (0, 1) for z in range(8)),
                    key=lambda bz: (dist2(TMS[m], PALETTES[bz[0]][bz[1]]), bz))
        v.append(z | br << 6)
    # Chosen rather than nearest (25 Oct): the MSX's light colours went to white.
    # Light blue -> bright cyan, light red -> bright red, light yellow -> bright
    # yellow.  (Enemy bullets, light red, stay white: spr_pmap in plat_spec.asm.)
    v[5], v[9], v[11] = 0x45, 0x42, 0x46
    out.append('    db ' + ','.join('0x%02X' % x for x in v))
    # Border colour from the MSX backdrop colour
    out.append('border_of:        ; MSX colour -> ZX border colour')
    out.append('    db ' + ','.join(str(min(range(8), key=lambda z: dist2(TMS[m], PALETTES[0][z]))) for m in range(16)))
    return out

# MSX keyboard matrix -> Spectrum key.  Spectrum half-rows (port high byte):
HALF = {'FE': 0, 'FD': 1, 'FB': 2, 'F7': 3, 'EF': 4, 'DF': 5, 'BF': 6, '7F': 7}
KEY = {  # Spectrum key name -> (half-row index, bit)
    'CS': (0, 0), 'Z': (0, 1), 'X': (0, 2), 'C': (0, 3), 'V': (0, 4),
    'A': (1, 0), 'S': (1, 1), 'D': (1, 2), 'F': (1, 3), 'G': (1, 4),
    'Q': (2, 0), 'W': (2, 1), 'E': (2, 2), 'R': (2, 3), 'T': (2, 4),
    '1': (3, 0), '2': (3, 1), '3': (3, 2), '4': (3, 3), '5': (3, 4),
    '0': (4, 0), '9': (4, 1), '8': (4, 2), '7': (4, 3), '6': (4, 4),
    'P': (5, 0), 'O': (5, 1), 'I': (5, 2), 'U': (5, 3), 'Y': (5, 4),
    'ENT': (6, 0), 'L': (6, 1), 'K': (6, 2), 'J': (6, 3), 'H': (6, 4),
    'SP': (7, 0), 'SS': (7, 1), 'M': (7, 2), 'N': (7, 3), 'B': (7, 4),
}
MSX_MATRIX = [  # rows 0-8, bits 0-7 (international layout)
    ['0', '1', '2', '3', '4', '5', '6', '7'],
    ['8', '9', None, None, None, None, None, None],
    [None, None, None, None, None, None, 'A', 'B'],
    ['C', 'D', 'E', 'F', 'G', 'H', 'I', 'J'],
    ['K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R'],
    ['S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z'],
    ['CS', None, None, None, None, 'H', None, None],     # SHIFT CTRL GRAPH CAPS CODE F1 F2 F3; F1 (pause) = H
    [None, 'C', None, None, None, None, None, 'ENT'],    # F4 F5 ESC TAB STOP BS SELECT RETURN; F5 (continue) = C
    ['SP', None, None, None, None, None, None, None],    # SPACE HOME INS DEL LEFT UP DOWN RIGHT
]
JOY = [  # PSG register 14 bits 0-5: up, down, left, right, trigger A, trigger B
    ['Q', '9'], ['A', '8'], ['O', '6'], ['P', '7'], ['SP', '0'], ['M'],
]

def keymaps():
    """kb_compute: kb_rows (8 half-rows, bit 0 = pressed) -> kb_cache, the
    nine MSX matrix rows then the joystick byte, all active low.  Grouped by
    half-row, so a half-row with nothing pressed costs one test."""
    maps = {}                   # half-row -> [(spectrum bit, kb_cache index, bit)]
    for n, row in enumerate(MSX_MATRIX):
        for bit, k in enumerate(row):
            if k is not None:
                h, kb = KEY[k]; maps.setdefault(h, []).append((kb, n, bit))
    for bit, ks in enumerate(JOY):
        for k in ks:
            h, kb = KEY[k]; maps.setdefault(h, []).append((kb, 9, bit))
    out = ['kb_compute:', '    push ix', '    ld ix,kb_cache', '    ld a,0xff']
    out += ['    ld (ix+%d),a' % n for n in range(9)]
    out += ['    ld (ix+9),0x3f']
    for h in sorted(maps):
        out += ['    ld a,(kb_rows+%d)' % h, '    cpl', '    and 0x1f', '    jr z,.h%d' % h]
        for kb, n, bit in sorted(maps[h]):
            out += ['    bit %d,a' % kb, '    jr z,$+6', '    res %d,(ix+%d)' % (bit, n)]
        out.append('.h%d:' % h)
    out += ['    pop ix', '    ret']
    return out

def screen_tables():
    # Cell row R (0-23): pixel address high byte offset and low byte base.
    out = ['row_hi:           ; cell row -> pixel address high byte (add screen base 0x40/0xC0)']
    out.append('    db ' + ','.join('0x%02X' % (((r & 0x18)) ) for r in range(24)))
    out.append('row_lo:           ; cell row -> pixel address low byte of column 0')
    out.append('    db ' + ','.join('0x%02X' % ((r & 7) << 5) for r in range(24)))
    return out

if __name__ == '__main__':
    lines = ['; generated by tables.py'] + tables() + keymaps()
    open(NEM_ROOT + '/spec/tables.asm', 'w').write('\n'.join(lines) + '\n')
    print('tables.asm written')
