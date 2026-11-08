"""Model of 1.0's rules.asm, the stage colour rules: for a tile of stage 2, 3, 6, 7
or 8 (third t, number i, MSX pattern and colour rows), what the Spectrum shows.

rule(stage, t, i, pat, col, dist) returns
  None                      the colour fit's result stands;
  ('paint', rows, attr)     these 8 rows and attribute (before tile_invert);
  ('recolour', f)           the fit's rows, its attribute A shown as f(A).
"""

def pixels(pat, col):
    return [[(col[y] >> 4) if pat[y] & (0x80 >> x) else (col[y] & 15) for x in range(8)] for y in range(8)]

def masks(pat, col, cols):
    out = []
    for y in range(8):
        fg, bg = col[y] >> 4, col[y] & 15
        m = (pat[y] if fg in cols else 0) | ((~pat[y] & 0xFF) if bg in cols else 0)
        out.append(m)
    return out

def counts(pat, col):
    c = [0] * 16
    for y in range(8):
        n = bin(pat[y]).count('1')
        c[col[y] >> 4] += n
        c[col[y] & 15] += 8 - n
    return c

def only(pat, col, allowed):
    return not any(masks(pat, col, set(range(16)) - set(allowed)))

STIP = [0x55 if y % 2 == 0 else 0xAA for y in range(8)]

def swap(a, frm, to):
    if a & 7 == frm: a = (a & 0xF8) | to
    if (a >> 3) & 7 == frm: a = (a & 0xC7) | (to << 3)
    return a

T2_ATTR = [0x05, 0x47, 0x05, 0x47, 0x05, 0x05, 0x47]

def rule(stage, t, i, pat, col, dist=0):
    if t == 2 and i < 0x44:
        return None
    c = counts(pat, col)
    if stage == 10 and only(pat, col, {0, 10, 11}) and c[0] <= 64 - 8:
        return ('paint', masks(pat, col, set(range(1, 16))), 0x06)   # bonus stage 10's balls: dark yellow
    if stage in (2, 9, 10, 11, 12):      # the bonus stages use stage 2's bricks
        k = i - 0x45
        if not 0 <= k < 7 or not only(pat, col, {0, 4, 5, 14, 15}):
            return None
        solid = masks(pat, col, set() if i == 0x49 else {14, 15})
        st = masks(pat, col, {4, 5})
        return ('paint', [solid[y] | (st[y] & STIP[y]) for y in range(8)], T2_ATTR[k])
    if stage == 3:
        if dist >= 0x195:               # the Moai section only
            return None
        mx = max(c[2:])
        if not mx:
            return None
        kind = None
        for y in range(8):
            for k in (col[y] >> 4, col[y] & 15):
                if kind is None and k >= 2 and c[k] == mx:
                    kind = k
        to = {4: 5, 5: 5, 9: 3}.get(kind)
        if to is None:
            return None
        return ('recolour', lambda a: swap(a, 7, to))
    if stage == 6:
        if not only(pat, col, {0, 6, 8, 9}) or c[0] == 64:
            return None
        return ('recolour', lambda a: swap(a, 7, 3) | 0x40)
    if stage == 7:
        if only(pat, col, {0, 2, 3, 4, 5, 7, 12}):
            if not (c[2] + c[3] + c[12]):
                if t >= 2 or c[7] or not (c[4] + c[5]):
                    return None
            if c[0] >= 25:
                return ('paint', masks(pat, col, set(range(1, 16))), 0x41)
            return ('paint', masks(pat, col, {2, 3, 7, 12}), 0x4C)
        if not only(pat, col, {0, 4, 5, 7, 14, 15}) or c[4] < 4 or not (c[14] + c[15]):
            return None
        light = masks(pat, col, {7, 14, 15})
        if c[0] >= 25:
            return ('paint', light, 0x07)
        nz = masks(pat, col, set(range(1, 16)))
        rows = []
        for y in range(8):
            near = (nz[y - 1] if y > 0 else 0) | (nz[y + 1] if y < 7 else 0)
            rows.append(light[y] | (~nz[y] & 0xFF & near))
        return ('paint', rows, 0x0F)
    if stage == 8:
        if only(pat, col, {0, 4, 5, 7, 14, 15}):
            if c[0] == 64 or not c[4]:
                return None
            if i == 0x58:
                return ('paint', masks(pat, col, set(range(1, 16))), 0x47)
            light = masks(pat, col, {7, 14, 15})
            if any(bin(m).count('1') >= 4 for m in light):
                b5 = masks(pat, col, {5})
                return ('paint', [light[y] | (b5[y] & STIP[y]) for y in range(8)], 0x4F)
            return ('paint', masks(pat, col, set(range(1, 16))), 0x41)
        if only(pat, col, {0, 6, 9, 10, 11}) and c[6]:
            def f(a):
                if not ({a & 7, (a >> 3) & 7} & {2, 6}):
                    return a
                return swap(swap(a, 7, 3), 6, 2) | 0x40
            return ('recolour', f)
        return None
    return None

def invert(rows, attr):
    """tile_invert: more than half the pixels set -> stored the other way round."""
    if attr & 7 == (attr >> 3) & 7:
        return rows, attr
    if sum(bin(r).count('1') for r in rows) < 33:
        return rows, attr
    a = (attr & 0xC0) | ((attr & 7) << 3) | ((attr >> 3) & 7)
    return [~r & 0xFF for r in rows], a
