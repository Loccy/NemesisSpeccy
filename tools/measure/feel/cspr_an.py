"""Compare pp_cspr.py runs: the shipped renderer and compiled sprites.
usage: cspr_an.py BASE.pkl CSPR.pkl"""
import pickle, sys, collections
def load(p): return pickle.load(open(p, 'rb'))
def summary(d, name):
    F = [x for x in d['FRAMES'] if x[1]]
    def tab(fr):
        t = sum(x[3] for x in fr); dr = sum(x[4] for x in fr); C = collections.Counter()
        for x in fr: C.update(x[5])
        work = sum(v for k, v in C.items() if k != 'wait')
        return dict(secs=len(fr) / 50, tps=t / (len(fr) / 50), drawn=dr / max(t, 1), pps=dr / (len(fr) / 50),
                    spr_pic=C['sprites'] / max(dr, 1), work_tick=work / max(t, 1), cells_pic=C['cells'] / max(dr, 1))
    win = []
    for i in range(0, len(F) - 50, 50):
        w = F[i:i + 50]
        if w[0][2] == w[-1][2] and w[-1][0] - w[0][0] == 49: win.append((sum(x[3] for x in w), w))
    win.sort(key=lambda t: t[0]); q = len(win) // 4
    st = d['stage_start']; ks = sorted(k for k in st if k[1] > 0)
    per = {a[1]: round((st[b][1] - st[a][1]) / ((st[b][0] - st[a][0]) / 50), 2) for a, b in zip(ks, ks[1:]) if a[0] == 1}
    out = dict(loop=tab(F), busy=tab([x for _, w in win[:q] for x in w]), quiet=tab([x for _, w in win[-q:] for x in w]), stages=per)
    print('==', name)
    for k in ('loop', 'busy', 'quiet'):
        v = out[k]
        print('  %-5s %6.0f s  %5.2f ticks/s  %4.1f%% drawn  %5.2f pictures/s  sprites %6.0f T a picture  cells %6.0f  all work %6.0f T a tick' % (
            k, v['secs'], v['tps'], 100 * v['drawn'], v['pps'], v['spr_pic'], v['cells_pic'], v['work_tick']))
    print('  ticks/s by stage', per)
    return out
b = summary(load(sys.argv[1]), 'shipped renderer')
dc = load(sys.argv[2]); c = summary(dc, 'compiled sprites')
sz = dc['sizes']; used = dc['used']
print('== code: distinct (pattern, offset) %d, %d bytes in all' % (len(sz), sum(sz.values())))
allc = collections.Counter()
for stg in sorted(used):
    u = used[stg]; allc.update(u)
    tot = sum(u.values()); by = sorted(u.items(), key=lambda kv: -kv[1])
    cum = 0; mark = {}
    for i, (k, n) in enumerate(by):
        cum += n
        for p in (0.5, 0.8, 0.9, 0.99):
            if p not in mark and cum >= p * tot: mark[p] = (i + 1, sum(sz[kk] for kk, _ in by[:i + 1]))
    pats = len(set(k[0] for k in u))
    print('  stage %2d: %3d patterns, %4d (pattern, offset), %6d bytes; draws covered: %s' % (
        stg, pats, len(u), sum(sz[k] for k in u), ', '.join('%d%% by %d (%d bytes)' % (100 * p, m[0], m[1]) for p, m in sorted(mark.items()))))
# by pattern alone (all its offsets), over the loop
pc = collections.Counter(); pb = collections.Counter()
for (pat, sh), n in allc.items(): pc[pat] += n
for (pat, sh), n in sz.items(): pb[pat] += n
tot = sum(pc.values()); cum = 0
print('  patterns by draws over the loop (bytes = all the offsets seen):')
for i, (pat, n) in enumerate(pc.most_common(12)):
    cum += n; print('   %2d  %5.1f%% of draws (cumulative %5.1f%%)  %5d bytes' % (i + 1, 100 * n / tot, 100 * cum / tot, pb[pat]))
