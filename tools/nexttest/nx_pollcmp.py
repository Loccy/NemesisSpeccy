"""Compare two nx_poll.py runs at each change of Konami's state or stage: the character rows (colours,
patterns) of the characters on show (in either run's name table), the sprite
patterns, and tile_cdirty/tile_pdirty for the characters on show.
usage: nx_pollcmp.py DIR_A DIR_B"""
import sys, os
A, B = sys.argv[1:3]
def rd(d, i):
    b = open(os.path.join(d, 'e%03d.bin' % i), 'rb').read()
    return dict(col=b[0:0x1800], pat=b[0x1800:0x3000], spr=b[0x3000:0x3800], bits=b[0x3800:0x3900], names=b[0x3900:0x3C00])
def changes(d):
    """The dumps taken on a change of state or stage or of the colours (not
    the periodic ones in play, whose timing differs between builds)."""
    out = []
    for l in open(os.path.join(d, 'events.txt')):
        e = l.split()
        if e[1] != 'periodic': out.append([e[0]] + e[2:])
    return out
ev, evb = changes(A), changes(B)
bad = 0
for e, f in zip(ev, evb):
    a, b = rd(A, int(e[0])), rd(B, int(f[0]))
    shown = set()
    for d in (a, b):
        for r in range(24):
            for c in range(32): shown.add((r // 8) * 256 + d['names'][r * 32 + c])
    out = []
    for t in ('col', 'pat'):
        ks = sorted(k for k in shown if a[t][k * 8:k * 8 + 8] != b[t][k * 8:k * 8 + 8])
        if ks: out.append('%s %d: %s' % (t, len(ks), ' '.join('%03X' % k for k in ks[:10])))
    if a['spr'] != b['spr']:
        out.append('sprite patterns %s' % ' '.join(str(n) for n in range(64) if a['spr'][n * 32:n * 32 + 32] != b['spr'][n * 32:n * 32 + 32]))
    bk = sorted(k for k in shown if ((a['bits'][k >> 3 if True else 0] | a['bits'][0x80 + (k >> 3)]) >> (k & 7) & 1) !=
                ((b['bits'][k >> 3] | b['bits'][0x80 + (k >> 3)]) >> (k & 7) & 1))
    if bk: out.append('marked %d: %s' % (len(bk), ' '.join('%03X' % k for k in bk[:10])))
    l2 = ''
    try:
        la = open(os.path.join(A, 'e%s.l2' % e[0]), 'rb').read(); lb = open(os.path.join(B, 'e%s.l2' % f[0]), 'rb').read()
        nd = [sum(1 for x, y in zip(la[s:s + 0xC000], lb[s:s + 0xC000]) if x != y) for s in (0, 0xC000)]
        l2 = '  [Layer 2: %d, %d pixels differ]' % tuple(nd)
        # colour entries one run uses and the other does not: a drawing
        # fault, not timing (the stars as blocks in entries E0-EF, 8 Nov)
        ua, ub = set(la), set(lb)
        if ua != ub:
            l2 += ' ENTRIES only in A: %s, only in B: %s' % (sorted(ua - ub)[:12], sorted(ub - ua)[:12])
    except OSError:
        pass
    print('%s/%s %s %s  %s%s' % (e[0], f[0], ' '.join(e[1:5]), '' if e[1:5] == f[1:5] else '(B: %s)' % ' '.join(f[1:5]),
                                 '; '.join(out) or 'same', l2))
    bad += bool(out)
print('%d of %d dumps differ' % (bad, min(len(ev), len(evb))))
