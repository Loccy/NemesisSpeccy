"""Analyse the three timelines: per frame (50 Hz) in play, the game tick the
picture shows.  Per stage of the first loop: seconds, game ticks a second,
new pictures a second, frames with no change, the picture's advance per
frame, how far the picture strays from steady motion, the slowest and
fastest second, and input lag.
usage: feel_an.py"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import pickle, statistics, collections, json, sys

def load_tl(path):
    d = pickle.load(open(path, 'rb'))
    tl = [(r[0], r[1], r[2], r[3]) for r in d['TL']]           # f, in play, stage, shown tick
    return tl, d['lag'], d['stage_start']

def load_nx(path):
    d = pickle.load(open(path, 'rb'))
    frames = d['frames']; renders = d['renders']
    byf = {r[0]: r for r in frames}
    tl = []; rendered = {}; j = 0
    for fr in frames:
        f, e000, st, dist, e003, pb, ticks = fr
        # renders that happened before this frame's interrupt: started after frame f-1's
        while j < len(renders) and renders[j][0] < f:
            rf, re3, rpb, ry = renders[j]
            base = byf.get(rf)
            if base is not None:
                cum = base[6] + ((re3 - base[4]) & 255)
                rendered[(rpb & 8) ^ 8] = cum
            j += 1
        tl.append((f, int(e000 == 5), st, rendered.get(pb & 8)))
    return tl, d['lag'], d['stage_start']

def analyse(tl, lag, start):
    ks = sorted(k for k in start if k[1] > 0)
    out = {}
    byf = {r[0]: r for r in tl}
    for a, b in zip(ks, ks[1:]):
        if a[0] != 1: continue
        fa, fb = start[a][0], start[b][0]
        seq = [byf[f] for f in range(fa, fb) if f in byf]
        play = [r for r in seq if r[1] and r[3] is not None]
        T = [r[3] for r in play]
        if len(T) < 100: continue
        adv = [y - x for x, y in zip(T, T[1:])]
        secs = (fb - fa) / 50
        ticks = T[-1] - T[0]
        still = sum(1 for x in adv if x == 0)
        new = len(adv) - still
        dist = collections.Counter(min(x, 6) for x in adv)
        W = 25
        dev = []
        for i in range(W, len(T) - W):
            m = sum(T[i - W:i + W + 1]) / (2 * W + 1)
            dev.append(T[i] - m)
        rms = (sum(x * x for x in dev) / len(dev)) ** 0.5
        persec = [T[i + 50] - T[i] for i in range(0, len(T) - 50)]
        # runs of frames with no change
        runs = []; r = 0
        for x in adv:
            if x == 0: r += 1
            else:
                if r: runs.append(r)
                r = 0
        chg = [i for i, x in enumerate(adv) if x]
        gaps = collections.Counter(min(b2 - a2, 8) for a2, b2 in zip(chg, chg[1:]))
        ng = sum(gaps.values())
        out[a[1]] = dict(gaps={k: round(100 * v / ng, 1) for k, v in sorted(gaps.items())},seconds=round(secs, 1), ticks_per_s=round(ticks / (len(T) / 50), 2),
                         pictures_per_s=round(new / (len(adv) / 50), 2),
                         still_pct=round(100 * still / len(adv), 1),
                         adv={k: round(100 * v / len(adv), 1) for k, v in sorted(dist.items())},
                         longest_still=max(runs) if runs else 0,
                         judder_rms=round(rms, 2),
                         slowest_s=min(persec), fastest_s=max(persec),
                         p5_s=sorted(persec)[len(persec) // 20], p50_s=sorted(persec)[len(persec) // 2],
                         p95_s=sorted(persec)[len(persec) * 19 // 20], over35_pct=round(100 * sum(1 for x in persec if x > 35) / len(persec), 1))
    if not out: return None
    tot = dict(seconds=round(sum(v['seconds'] for v in out.values()), 1))
    tot['ticks_per_s'] = round(sum(v['ticks_per_s'] * v['seconds'] for v in out.values()) / tot['seconds'], 2)
    tot['pictures_per_s'] = round(sum(v['pictures_per_s'] * v['seconds'] for v in out.values()) / tot['seconds'], 2)
    tot['still_pct'] = round(sum(v['still_pct'] * v['seconds'] for v in out.values()) / tot['seconds'], 1)
    tot['judder_rms'] = round(sum(v['judder_rms'] * v['seconds'] for v in out.values()) / tot['seconds'], 2)
    tot['slowest_s'] = min(v['slowest_s'] for v in out.values())
    out['loop'] = tot
    L = sorted(lag)
    out['lag'] = dict(n=len(L), mean=round(statistics.mean(L), 2), median=round(statistics.median(L), 2),
                      p90=round(L[int(len(L) * 0.9)], 2), max=round(L[-1], 2)) if L else None
    return out

if __name__ == '__main__':
    res = {}
    for name, path, kind in (('MSX', (_SCRATCH + '/night2/feelmsx.tl.pkl'), 'tl'),
                             ('128K', (_SCRATCH + '/night2/feel128.json.tl.pkl'), 'tl'),
                             ('Next', (_SCRATCH + '/night2/nxf/feelnx2.raw.pkl'), 'nx')):
        try:
            tl, lag, st = (load_tl if kind == 'tl' else load_nx)(path)
        except FileNotFoundError:
            continue
        res[name] = analyse(tl, lag, st)
    json.dump(res, open((_SCRATCH + '/night2/feel_results.json'), 'w'), indent=1)
    for name, r in res.items():
        print('==', name)
        if r is None: continue
        for k, v in r.items(): print(' ', k, v)
