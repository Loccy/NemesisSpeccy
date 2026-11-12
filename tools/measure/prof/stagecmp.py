"""Two profiles, one stage: T-states a tick by function, the biggest changes.  stagecmp.py A.pkl B.pkl STAGE [N]"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, pickle, collections
sys.path.insert(0, (_SCRATCH + '/work'))
from labels import cat
A = pickle.load(open(sys.argv[1], 'rb')); B = pickle.load(open(sys.argv[2], 'rb')); ST = int(sys.argv[3]); N = int(sys.argv[4]) if len(sys.argv) > 4 else 25
def stage(D):
    all_ = []; seen8 = False
    for x in D['SECS']:                     # the first loop alone (as an2.py)
        if x[1] == 5 and x[2] == 8: seen8 = True
        if seen8 and x[1] == 5 and x[2] == 1: break
        all_.append(x)
    secs = [x for x in all_ if x[1] == 5 and (ST == 0 or x[2] == ST)]
    ft = collections.Counter()
    for x in secs: ft.update(x[6])
    ticks = sum(x[4] for x in secs); pics = sum(x[5] for x in secs)
    return ft, ticks, pics, len(secs)
fa, ta, pa, sa = stage(A); fb, tb, pb, sb = stage(B)
print('stage %d: %d s, %d ticks, %d pictures  |  %d s, %d ticks, %d pictures' % (ST, sa, ta, pa, sb, tb, pb))
print('T a tick: %d -> %d' % (sum(fa.values())/ta, sum(fb.values())/tb))
d = {n: fb.get(n, 0)/tb - fa.get(n, 0)/ta for n in set(fa) | set(fb)}
for n in sorted(d, key=lambda n: -abs(d[n]))[:N]:
    print('  %-9s %-26s %7d -> %7d  %+6d' % (cat(n), n, fa.get(n, 0)/ta, fb.get(n, 0)/tb, d[n]))
