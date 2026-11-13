import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, pickle, collections
sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from labels import Labels, cat
D = pickle.load(open(sys.argv[1], 'rb')); TOP = int(sys.argv[2]) if len(sys.argv) > 2 else 60
LB = Labels(D['sna'], D['sym']); func = LB.func
def first_loop(secs):
    """The seconds of the first loop: up to stage 1 coming round again after stage 8
    (prof2.py runs on to frame 80,000, into the second loop when a build is quick)."""
    out = []; seen8 = False
    for x in secs:
        if x[1] == 5 and x[2] == 8: seen8 = True
        if seen8 and x[1] == 5 and x[2] == 1: break
        out.append(x)
    return out
SECS = [x for x in first_loop(D['SECS']) if x[1] == 5]
def summarize(secs, title, top=TOP, show=True):
    ticks = sum(x[4] for x in secs); pics = sum(x[5] for x in secs)
    ft = collections.Counter()
    for x in secs: ft.update(x[6])
    tot = sum(ft.values()); ct = collections.Counter()
    for n, t in ft.items(): ct[cat(n)] += t
    print('\n== %s: %d s, %.2f ticks/s, %.2f pictures/s, drawn %.0f%%, %d T per tick' % (title, len(secs), ticks/len(secs), pics/len(secs), 100*pics/ticks, tot/ticks))
    print('  ' + '  '.join('%s %d (%.1f%%)' % (c, t/ticks, 100*t/tot) for c, t in ct.most_common()))
    if show:
        for n, t in ft.most_common(top):
            print('    %-9s %-24s %7d /tick %5.2f%%' % (cat(n), n, t/ticks, 100*t/tot))
    return ft, ticks, pics, tot
allr = summarize(SECS, 'whole loop')
srt = sorted(SECS, key=lambda x: x[4]); q = srt[:len(srt)//4]
busy = summarize(q, 'busiest quarter (fewest ticks)')
for st in range(1, 9):
    summarize([x for x in SECS if x[2] == st], 'stage %d' % st, show=False)
pickle.dump(dict(all=allr, busy=busy), open(sys.argv[1] + '.sum', 'wb'))
