"""Compare two fulltest.py runs (A, B: say 1.0N and the native build) at the
points both reach in the same order: each stage's start, each boss gone, the
ending's dumps, the second loop's start.  For each: the characters on show
(in either run's name table) whose rows differ, the sprite patterns that
differ, the characters on show marked in one run only, and Layer 2: pixels
that differ (both screens) and colour entries one run uses and the other
does not (a drawing fault, not timing).  Stars (F6, F7) twinkle: their
pattern rows are left out.
usage: nx_ftcmp.py DIR_A DIR_B"""
import os, re, sys
A, B = sys.argv[1:3]
KEEP = re.compile(r'^d\d+_(s\d+_start|s\d+_bossgone|end\d+_\d+_[0-9A-F]+|loop\d+_s1)$')
def points(d):
    out = []
    for f in sorted(os.listdir(d)):
        if f.endswith('.bin') and KEEP.match(f[:-4]):
            tag = f[:-4].split('_', 1)[1]
            out.append((re.sub(r'^(end\d+_\d+)_.*$', r'\1', tag), os.path.join(d, f[:-4])))
    return out
def rd(f):
    b = open(f + '.bin', 'rb').read()
    return dict(col=b[0:0x1800], pat=b[0x1800:0x3000], spr=b[0x3000:0x3800], bits=b[0x3800:0x3900],
                names=b[0x3900:0x3C00], l2=open(f + '.l2', 'rb').read())
pa, pb = points(A), points(B)
tb = {}
for t, f in pb: tb.setdefault(t, []).append(f)
seen = {}; bad = 0; n = 0
for t, fa in pa:
    i = seen.get(t, 0); seen[t] = i + 1
    if t not in tb or i >= len(tb[t]):
        print('%-14s only in A' % t); continue
    a, b = rd(fa), rd(tb[t][i]); n += 1
    shown = set()
    for x in (a, b):
        for r in range(24):
            for c in range(32): shown.add((r // 8) * 256 + x['names'][r * 32 + c])
    out = []
    for k in ('col', 'pat'):
        ks = sorted(c for c in shown if a[k][c * 8:c * 8 + 8] != b[k][c * 8:c * 8 + 8]
                    and not (k == 'pat' and c & 0xFF in (0xF6, 0xF7)))
        if ks: out.append('%s %d: %s' % (k, len(ks), ' '.join('%03X' % c for c in ks[:8])))
    sp = [i for i in range(64) if a['spr'][i * 32:i * 32 + 32] != b['spr'][i * 32:i * 32 + 32]]
    if sp: out.append('sprite patterns ' + ' '.join(map(str, sp)))
    def mk(x, c): return ((x['bits'][c >> 3] | x['bits'][0x80 + (c >> 3)]) >> (c & 7)) & 1
    m = sorted(c for c in shown if mk(a, c) != mk(b, c) and c & 0xFF not in (0xF6, 0xF7))
    if m: out.append('marked %d: %s' % (len(m), ' '.join('%03X' % c for c in m[:8])))
    px = [sum(1 for x, y in zip(a['l2'][s:s + 0xC000], b['l2'][s:s + 0xC000]) if x != y) for s in (0, 0xC000)]
    ua, ub = set(a['l2']), set(b['l2'])
    ent = '' if ua == ub else '; ENTRIES only in A %s, only in B %s' % (sorted(ua - ub)[:10], sorted(ub - ua)[:10])
    if out or ent: bad += 1
    print('%-14s %s  [Layer 2: %d, %d pixels]%s' % (t, '; '.join(out) or 'same', px[0], px[1], ent))
for t in tb:
    if t not in seen: print('%-14s only in B' % t)
print('%d points compared, %d with differences' % (n, bad))
