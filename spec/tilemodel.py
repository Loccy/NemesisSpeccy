"""1.0's conversion of an MSX character to a Spectrum tile, as a pure function
(the native 128K plan's build-time converter; claude/native-128k-plan.md).

convert(pat, col, third, ch, state, stage, dist) -> (rows, attr)
  pat, col: the character's 8 pattern and 8 colour bytes (MSX)
  state, stage, dist: Konami's state (E000), stage (E061) and distance
  (E063-E064) when 1.0 converts it.

Follows convert.asm's order: the colour fit (convert_tile, modelled by
fit_model.heur_q), bar_style (barstyle.asm), then tile_post (plat_spec.asm):
the title logo (logo_tile) on the title, otherwise the stage colour rules
(rules.asm, modelled by stage_rules.rule) and tile_invert, then the nuke
capsule's cyan.  Not modelled: the dissolve's own path (dz_tile, conv_dz) and
the pattern-only recolouring of the stars (recolour_tile), which the native
build replaces.
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

def convert(pat, col, third, ch, state, stage, dist):
    t = heur_q(tuple(zip(pat, col)))
    rows, attr = list(t[:8]), t[8]
    rows, attr = bar_style(pat, col, third, ch, rows, attr)
    if state < 2 and third < 2 and ch >= 0x8D:
        return logo_tile(pat, col)
    ru = rule(stage, third, ch, list(pat), list(col), dist)
    if ru:
        if ru[0] == 'paint': rows, attr = list(ru[1]), ru[2]
        else: attr = ru[1](attr)
    rows, attr = invert(rows, attr)
    rows = list(rows)
    if 0x77 <= ch <= 0x7A:
        if attr & 0x38 == 0: attr = (attr & 0xB8) | 0x45
        else: attr = (attr & 0x87) | 0x68
    return rows, attr
