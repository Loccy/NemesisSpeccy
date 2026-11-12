"""Report on census_gfx.py's runs: python3 census_report.py runA.pkl runB.pkl"""
import sys, pickle, collections
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'spec'))
runs = [(p, pickle.load(open(p, 'rb'))) for p in sys.argv[1:]]
STATE = {0: 'logo/title', 1: 'title', 2: 'attract', 3: 'start', 4: 'pre-stage', 5: 'play', 6: '6', 7: 'game over', 8: '8', 9: '9'}
def h(x): return '%04X' % x if isinstance(x, int) else str(x)

print('== 1. Writes to the pattern, colour and sprite pattern tables')
agg = collections.defaultdict(lambda: [0, set(), set()])
for p, d in runs:
    for (rg, ld, caller, st, sg), n in d['writes'].items():
        if rg in ('col', 'pat', 'spat'):
            a = agg[(ld, h(caller), rg)]; a[0] += n; a[1].add(st); a[2].add(sg)
for (ld, caller, rg), (n, sts, sgs) in sorted(agg.items()):
    print('  %-16s from %s  %-4s %7d bytes  states %s  stages %s' % (ld, caller, rg, n, sorted(sts), sorted(sgs)))

print('\n== 2. Characters and sprite patterns shown in play that the stage\'s own loads did not write')
OWN = {'stage_gfx', 'bigcore', 'twinkle', 'dissolve', 'dissolve_chunk'}
res = collections.defaultdict(lambda: collections.Counter())
for p, d in runs:
    for (st, sg, kind, idx), provs in d['shown'].items():
        if st != 5: continue
        for pv in provs:
            bad = sorted(set((e[0], h(e[1]), e[3]) for e in pv if not (e[0] in OWN and e[3] == sg)))
            if bad:
                res[(sg, kind)][(idx, tuple(bad))] += 1
for (sg, kind), c in sorted(res.items()):
    print('  stage %2d %s: %d shown with bytes from elsewhere' % (sg, kind, len(c)))
    for (idx, bad), n in sorted(c.items())[:40]:
        name = ('third %d char %02X' % divmod(idx, 256)) if kind == 'chr' else 'pattern %d' % idx
        print('     %-18s %s' % (name, ' + '.join('%s %s (stage %d)' % b for b in bad)))
if not res: print('  none')

print('\n== 2b. Screens that are not play: where their characters come from')
for p, d in runs:
    pass
src = collections.defaultdict(collections.Counter)
for p, d in runs:
    for (st, sg, kind, idx), provs in d['shown'].items():
        if st == 5: continue
        for pv in provs:
            for e in pv: src[(st, kind)][(e[0], h(e[1]), e[2], e[3])] += 1
for (st, kind), c in sorted(src.items()):
    print('  state %d (%s) %s:' % (st, STATE.get(st, st), kind), ', '.join('%s %s st%d sg%d x%d' % (a, b, s, g, n) for (a, b, s, g), n in c.most_common(12)))

print('\n== 3. Stage 3: characters first shown at distance 195h or later')
late = collections.defaultdict(set); early = collections.defaultdict(set)
for p, d in runs:
    for (k, pv), dist in d['first_dist3'].items():
        (late if dist >= 0x195 else early)[k].add((p, dist))
both = sorted(set(late) & set(early)); only_late = sorted(set(late) - set(early))
print('  first shown only late: %d characters; late in one run or pass and early in another: %d' % (len(only_late), len(both)))
try:
    import gfxcap_states
except Exception:
    pass
import pickle as _p
S = _p.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'spec', 'vram_states.pkl'), 'rb'))[('stage', 3)]
from stage_rules import rule
def ruled(k):
    th, ch = divmod(k, 256); o = th * 0x800 + ch * 8
    pat = [S[0x2000 + o + l] for l in range(8)]; col = [S[o + l] for l in range(8)]
    return rule(3, th, ch, pat, col, 0) is not None
for k in only_late:
    if ruled(k): print('    rule would apply, first shown late: third %d char %02X' % divmod(k, 256), sorted(late[k])[:3])
for k in both:
    if ruled(k): print('    rule would apply, early and late: third %d char %02X' % divmod(k, 256))

print('\n== 4. Loader RAM read by other code before being written again')
c = collections.Counter()
for p, d in runs:
    for (a, pc, ld, st, sg), n in d['scratch_reads'].items():
        c[(a, pc, ld)] += n
byaddr = collections.defaultdict(list)
for (a, pc, ld), n in sorted(c.items()): byaddr[(ld, pc)].append(a)
for (ld, pc), addrs in sorted(byaddr.items()):
    print('  written by %-12s read at %04X: %s' % (ld, pc, ' '.join('%04X' % a for a in addrs[:16]) + (' ...(%d)' % len(addrs) if len(addrs) > 16 else '')))
for p, d in runs:
    print('  %s: loaders wrote %s' % (p, {k: len(v) for k, v in d['scratch_all'].items()}))
    print('  %s: deaths %s' % (p, d['deaths']))
