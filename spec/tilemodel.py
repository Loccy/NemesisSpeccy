"""1.0's conversion of an MSX character to a Spectrum tile, as a pure function
(the build-time converter of the build without MSX graphics, 1.1).

convert(pat, col, third, ch, state, stage, dist) -> (rows, attr)
  pat, col: the character's 8 pattern and 8 colour bytes (MSX)
  state, stage, dist: Konami's state (E000), stage (E061) and distance
  (E063-E064) when 1.0 converts it.

Follows convert.asm's order: the colour fit (convert_tile, modelled by
fit_model.heur_q), bar_style (1.0's barstyle.asm), then tile_post (1.0's plat_spec.asm):
the title logo (logo_tile) on the title, otherwise the stage colour rules
(1.0's rules.asm, modelled by stage_rules.rule) and tile_invert, then the nuke
capsule's cyan.  dz_post models the dissolve's own path (dz_tile, conv_dz)
for its colour pass.  Not modelled: the pattern-only recolouring of the
stars (recolour_tile), which the native build replaces.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fit_model import heur_q
from stage_rules import rule, invert

BAR_PLAIN = 0x40 | 1 << 3 | 7
BAR_LIT = 0x40 | 0 << 3 | 6

def bar_style(pat, col, third, ch, rows, attr):
    if third != 2: return rows, attr
    if not (ch == 0x0C or 0x15 <= ch < 0x43): return rows, attr
    c4 = col[4]
    if c4 & 0xF0 == 0x40 or c4 & 15 == 4: lit = False
    elif c4 & 0xF0 == 0xA0 or c4 & 15 == 0x0A: lit = True
    else: return rows, attr
    gap = 0xFF
    if not lit and (ch == 0x0C or (ch < 0x29 and (ch - 0x15) & 3 == 3)): gap = 0xFE
    out = []
    for r in range(8):
        c, h = pat[r], col[r]
        d = c if (h >> 4) >= 2 else 0
        if (h & 15) >= 2: d |= ~c & 0xFF
        if lit: out.append(0 if r == 0 else d)
        else: out.append((~d & gap) & 0xFF if 0 <= r - 2 < 5 else 0)
    return out, (BAR_LIT if lit else BAR_PLAIN)

def logo_tile(pat, col):
    fgs = [c >> 4 for c in col]
    cyan = any(p and f in (5, 7) for p, f in zip(pat, fgs))
    rows = []
    for r in range(8):
        st = fgs[r] == 5 or (fgs[r] == 4 and cyan)
        rows.append(pat[r] & ((0xAA if (8 - r) & 1 else 0x55) if st else 0xFF))
    return rows, (0x45 if cyan else 0x47)

LAST_INVERTED = False

def convert(pat, col, third, ch, state, stage, dist):
    global LAST_INVERTED
    LAST_INVERTED = False
    t = heur_q(tuple(zip(pat, col)))
    rows, attr = list(t[:8]), t[8]
    rows, attr = bar_style(pat, col, third, ch, rows, attr)
    if state < 2 and third < 2 and ch >= 0x8D:
        return logo_tile(pat, col)
    ru = rule(stage, third, ch, list(pat), list(col), dist)
    if ru:
        if ru[0] == 'paint': rows, attr = list(ru[1]), ru[2]
        else: attr = ru[1](attr)
    a0 = attr
    rows, attr = invert(rows, attr)
    rows = list(rows)
    LAST_INVERTED = attr != a0      # stored the other way round (the dissolve needs to know)
    if 0x77 <= ch <= 0x7A:
        if attr & 0x38 == 0: attr = (attr & 0xB8) | 0x45
        else: attr = (attr & 0x87) | 0x68
    return rows, attr

def dz_post(pat, col, rows, attr):
    """1.0's tile once Konami's dissolve has made every background black (its
    colour pass: the colours ANDed with F0), from the tile as it was (rows,
    attr): dz_tile (1.0's convert_e.asm).  The colour that showed the foreground
    (the old ink, or the old paper if it drew more of the pattern's pixels)
    becomes the ink on black paper, bright kept; a row's pixels stay if its
    foreground colour is strictly nearer that ink than black."""
    from fit_model import D
    a = attr & 0x7F
    if a & 0x38 == 0: paper = False
    elif a & 7 == 0: paper = True
    else:
        e = 0
        for r in range(8):
            for x in range(8):
                if pat[r] & (0x80 >> x):
                    e += 1 if rows[r] & (0x80 >> x) else -1
        paper = (e & 0x80) != 0
    c = (a >> 3) & 7 if paper else a & 7
    br = 1 if a & 0x40 else 0
    out = [pat[r] & (0xFF if c and D[br][col[r] >> 4][c] < D[br][col[r] >> 4][0] else 0) for r in range(8)]
    return out, (a & 0x40) | c
