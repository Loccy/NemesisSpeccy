import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, pickle, collections
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from labels import Labels, cat
A = pickle.load(open(sys.argv[1], 'rb')); B = pickle.load(open(sys.argv[2], 'rb'))
LB = Labels(A['sna'], A['sym']); func = LB.func; syms = LB.syms
def tot(D):
    ft = collections.Counter(); 
    for k, v in D['acc'].items(): ft[func(k)] += v
    ticks = D['cnt'][syms['pm_tick']]; pics = D['cnt'][syms['pm_render']]
    fc = collections.Counter()
    for p, d in LB.fstart.items():
        for a, n in d.items(): fc[n] += D['cnt'].get(a if p == -1 else a | p << 16, 0)
    return ft, fc, ticks, pics
fa, ca, ta, pa = tot(A); fb, cb, tb, pb = tot(B)
print('contended: ticks %d pictures %d T/tick %d   uncontended: ticks %d pictures %d T/tick %d' % (ta, pa, sum(fa.values())/ta, tb, pb, sum(fb.values())/tb))
# per category, normalised per tick (konami, track, paging, ...) or per picture (sprites, cells, stars)
ca_, cb_ = collections.Counter(), collections.Counter()
for n, t in fa.items(): ca_[cat(n)] += t
for n, t in fb.items(): cb_[cat(n)] += t
print('%-10s %10s %10s %8s' % ('category', 'contended', 'uncont.', 'extra'))
for c in sorted(ca_, key=lambda c: -ca_[c]):
    per = ('pic', pa, pb) if c in ('sprites', 'cells', 'stars') else ('tick', ta, tb)
    x, y = ca_[c]/per[1], cb_[c]/per[2]
    print('%-10s %10d %10d %+7.1f%%  per %s' % (c, x, y, 100*(x-y)/y if y else 0, per[0]))
print('\nfunctions: T per call, contended vs not (those over 300 T/tick):')
rows = []
for n, t in fa.items():
    if t/ta < 300 or not ca[n] or not cb[n]: continue
    x = t/ca[n]; y = fb[n]/cb[n]
    rows.append((t/ta, n, x, y))
for tt, n, x, y in sorted(rows, reverse=True)[:60]:
    print('  %-9s %-22s %7d T/tick  %7.0f vs %7.0f T/call  %+6.1f%%   lost %5d T/tick' % (cat(n), n, tt, x, y, 100*(x-y)/y, tt*(1-y/x)))
