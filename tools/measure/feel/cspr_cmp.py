"""Compare pp_cspr.py runs side by side, with the slow moments as well as
the averages.  usage: cspr_cmp.py NAME=PKL ..."""
import pickle, sys, collections
rows = []
for arg in sys.argv[1:]:
    name, p = arg.split('=', 1); d = pickle.load(open(p, 'rb'))
    F = [x for x in d['FRAMES'] if x[1]]
    t = sum(x[3] for x in F); dr = sum(x[4] for x in F); C = collections.Counter()
    for x in F: C.update(x[5])
    sec = []                                     # per second in play (50 frames, one stage)
    for i in range(0, len(F) - 50, 50):
        w = F[i:i + 50]
        if w[0][2] == w[-1][2] and w[-1][0] - w[0][0] == 49: sec.append((sum(x[3] for x in w), sum(x[4] for x in w)))
    ts = sorted(a for a, b in sec); ps = sorted(b for a, b in sec)
    q = len(sec) // 4; busy = sorted(sec)[:q]
    pct = lambda L, p: L[int(len(L) * p)]
    sz = d.get('sizes', {}); used = collections.Counter()
    for u in d.get('used', {}).values(): used.update(u)
    comp = sum(used.values())
    rows.append((name, dict(secs=len(F) / 50, tps=t / (len(F) / 50), pps=dr / (len(F) / 50), drawn=100 * dr / t,
                            spr=C['sprites'] / dr, busy_tps=sum(a for a, b in busy) / q, busy_pps=sum(b for a, b in busy) / q,
                            t5=pct(ts, 0.05), t10=pct(ts, 0.10), p5=pct(ps, 0.05), p10=pct(ps, 0.10),
                            code=sum(sz.values()), comp=comp)))
keys = [('secs', 'loop in play, s', '%.0f'), ('tps', 'ticks a second', '%.2f'), ('pps', 'pictures a second', '%.2f'),
        ('drawn', 'ticks drawn, %', '%.1f'), ('spr', 'sprites, T a picture', '%.0f'),
        ('busy_tps', 'busiest quarter: ticks/s', '%.2f'), ('busy_pps', 'busiest quarter: pictures/s', '%.2f'),
        ('t5', 'slowest 5% of seconds: ticks', '%d'), ('t10', 'slowest 10%: ticks', '%d'),
        ('p5', 'fewest-picture 5%: pictures', '%d'), ('p10', 'fewest-picture 10%: pictures', '%d'),
        ('code', 'compiled code, bytes', '%d'), ('comp', 'sprites drawn by compiled code', '%d')]
print('%-32s' % '' + ''.join('%14s' % n for n, _ in rows))
for k, label, fmt in keys:
    print('%-32s' % label + ''.join('%14s' % (fmt % r[k]) for _, r in rows))
