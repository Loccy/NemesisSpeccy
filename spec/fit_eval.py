import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, pickle, collections
sys.path.insert(0,NEM_ROOT + '/w31/tools')
from convert import colour_fit, PALETTES, dist2
from extract import TMS
S = pickle.load(open('vram_states.pkl','rb'))
NEAR = [[min(range(8), key=lambda z: dist2(TMS[m], PALETTES[br][z])) for m in range(16)] for br in (0,1)]
def heur(rows):
    counts = collections.Counter()
    for p, c in rows:
        n = bin(p).count('1'); counts[c >> 4] += n; counts[c & 15] += 8 - n
    best = None
    for br in (0, 1):
        pal = PALETTES[br]
        cands = sorted(set(NEAR[br][m] for m in counts))
        for ink in cands:
            for paper in cands:
                err = sum(n * min(dist2(TMS[m], pal[ink]), dist2(TMS[m], pal[paper])) for m, n in counts.items())
                attr = ink | paper << 3 | br << 6
                key = (err, ink == paper, (ink != 7 and paper != 0), attr)
                if best is None or key < best[0]: best = (key, ink, paper, br)
    _, ink, paper, br = best; pal = PALETTES[br]
    bits = []
    for p, c in rows:
        v = 0
        for i in range(8):
            m = (c >> 4) if p & (128 >> i) else (c & 15)
            if ink != paper and dist2(TMS[m], pal[ink]) < dist2(TMS[m], pal[paper]): v |= 128 >> i
        bits.append(v)
    return bytes(bits) + bytes([ink | paper << 3 | br << 6])
def err_of(rows, t):
    bits, attr = t[:8], t[8]; ink = attr & 7; paper = (attr >> 3) & 7; pal = PALETTES[attr >> 6 & 1]; e = 0
    for (p, c), b in zip(rows, bits):
        for i in range(8):
            m = (c >> 4) if p & (128 >> i) else (c & 15)
            z = ink if b & (128 >> i) else paper
            e += dist2(TMS[m], pal[z])
    return e
seen = set(); same = 0; tot = 0; e1 = e2 = 0; worse = []
for k, vr in S.items():
    for th in range(3):
        for ch in range(256):
            o = th * 0x800 + ch * 8
            rows = tuple((vr[0x2000 + o + l], vr[o + l]) for l in range(8))
            if rows in seen: continue
            seen.add(rows)
            pix = []
            for p, c in rows: pix.extend((c >> 4) if p & (128 >> i) else (c & 15) for i in range(8))
            a = colour_fit(tuple(pix)); b = heur(rows)
            tot += 1; same += a == b
            ea, eb = err_of(rows, a), err_of(rows, b); e1 += ea; e2 += eb
            if eb > ea: worse.append((eb - ea, k, th, ch))
print('distinct tiles', tot, 'identical result', same, 'total error full fit', e1, 'heuristic', e2)
worse.sort(reverse=True); print('worst:', worse[:8], 'count worse', len(worse))

# ---- H2: no multiplications ----
NEAR16 = [min(((br, z) for br in (0, 1) for z in range(8)), key=lambda bz: (dist2(TMS[m], PALETTES[bz[0]][bz[1]]), bz)) for m in range(16)]
def heur2(rows):
    counts = collections.Counter()
    for p, c in rows:
        n = bin(p).count('1'); fg = (c >> 4) or 1; bg = (c & 15) or 1
        counts[fg] += n; counts[bg] += 8 - n
    zc = collections.Counter()
    for m, n in counts.items():
        if n: zc[NEAR16[m]] += n
    top = [bz for bz, n in sorted(zc.items(), key=lambda kv: (-kv[1], kv[0]))]
    br = top[0][0]; pal = PALETTES[br]
    a = top[0][1]
    if len(top) > 1:
        b = top[1][1] if top[1][0] == br else min(range(8), key=lambda z: dist2(PALETTES[top[1][0]][top[1][1]], pal[z]))
    else: b = a
    # orientation: as the full fit's tie-break
    best = None
    for ink, paper in ((a, b), (b, a)):
        key = (ink == paper, (ink != 7 and paper != 0), ink | paper << 3 | br << 6)
        if best is None or key < best[0]: best = (key, ink, paper)
    _, ink, paper = best
    bits = []
    for p, c in rows:
        v = 0
        for i in range(8):
            m = ((c >> 4) or 1) if p & (128 >> i) else ((c & 15) or 1)
            if ink != paper and dist2(TMS[m], pal[ink]) < dist2(TMS[m], pal[paper]): v |= 128 >> i
        bits.append(v)
    return bytes(bits) + bytes([ink | paper << 3 | br << 6])
seen = set(); same = 0; tot = 0; e1 = e3 = 0
for k, vr in S.items():
    for th in range(3):
        for ch in range(256):
            o = th * 0x800 + ch * 8
            rows = tuple((vr[0x2000 + o + l], vr[o + l]) for l in range(8))
            if rows in seen: continue
            seen.add(rows)
            pix = []
            for p, c in rows: pix.extend((c >> 4) if p & (128 >> i) else (c & 15) for i in range(8))
            a = colour_fit(tuple(pix)); b = heur2(rows)
            tot += 1; same += a == b; e1 += err_of(rows, a); e3 += err_of(rows, b)
print('H2: identical', same, 'of', tot, 'error full', e1, 'H2', e3, 'ratio %.3f' % (e3 / e1))

# ---- H1q: H1 with 16-bit arithmetic (D = dist2 >> SH), exactly as the Z80 will do it ----
def make_tables(SH):
    D = [[[dist2(TMS[m], PALETTES[br][z]) >> SH for z in range(8)] for m in range(16)] for br in (0, 1)]
    NEARq = [[min(range(8), key=lambda z: (D[br][m][z], z)) for m in range(16)] for br in (0, 1)]
    return D, NEARq
def heur_q(rows, D, NEARq):
    counts = [0] * 16
    for p, c in rows:
        n = bin(p).count('1'); counts[c >> 4] += n; counts[c & 15] += 8 - n
    present = [m for m in range(16) if counts[m]]
    best = None
    for br in (0, 1):
        cands = []
        for m in present:
            z = NEARq[br][m]
            if z not in cands: cands.append(z)
        cands.sort()
        for ink in cands:
            for paper in cands:
                err = sum(counts[m] * min(D[br][m][ink], D[br][m][paper]) for m in present)
                err = min(err, 65535)
                key = (err, ink == paper, (ink != 7 and paper != 0), ink | paper << 3 | br << 6)
                if best is None or key < best[0]: best = (key, ink, paper, br)
    _, ink, paper, br = best
    bits = []
    for p, c in rows:
        fgb = ink != paper and D[br][c >> 4][ink] < D[br][c >> 4][paper]
        bgb = ink != paper and D[br][c & 15][ink] < D[br][c & 15][paper]
        bits.append((p if fgb else 0) | ((~p & 255) if bgb else 0))
    return bytes(bits) + bytes([ink | paper << 3 | br << 6])
for SH in (7, 8, 9):
    D, NQ = make_tables(SH)
    seen = set(); same = 0; tot = 0; e1 = e3 = 0
    for k, vr in S.items():
        for th in range(3):
            for ch in range(256):
                o = th * 0x800 + ch * 8
                rows = tuple((vr[0x2000 + o + l], vr[o + l]) for l in range(8))
                if rows in seen: continue
                seen.add(rows)
                pix = []
                for p, c in rows: pix.extend((c >> 4) if p & (128 >> i) else (c & 15) for i in range(8))
                a = colour_fit(tuple(pix)); b = heur_q(rows, D, NQ)
                tot += 1; same += a == b; e1 += err_of(rows, a); e3 += err_of(rows, b)
    print('H1q SH=%d: identical %d of %d, error ratio %.4f' % (SH, same, tot, e3 / e1))
