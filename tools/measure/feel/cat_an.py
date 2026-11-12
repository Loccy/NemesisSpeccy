"""Where a tick's time goes, from pp_cat.py's per-frame category totals.
usage: cat_an.py PKL"""
import pickle, sys, collections
d = pickle.load(open(sys.argv[1], 'rb'))
F = [x for x in d['FRAMES'] if x[1]]               # in play
ORDER = ['konami', 'sprites', 'cells', 'stars', 'track', 'paging', 'standins', 'sound', 'interrupt/flip',
         'input', 'loads', 'convert', 'other', 'wait/pace']
def table(frames, title):
    C = collections.Counter(); ticks = sum(x[3] for x in frames); drawn = sum(x[4] for x in frames)
    for x in frames: C.update(x[5])
    tot = sum(C.values()); work = tot - C['wait/pace']
    print('%s: %d s, %.1f ticks/s, %.0f%% of ticks drawn, busy %.0f%% of the time' % (
        title, len(frames) / 50, ticks / (len(frames) / 50), 100 * drawn / max(ticks, 1), 100 * work / tot))
    for k in ORDER:
        if C[k]: print('   %-15s %7.0f T a tick  %5.1f%% of work' % (k, C[k] / ticks, 100 * C[k] / work if k != 'wait/pace' else 0))
    print('   %-15s %7.0f T a tick (budget for 25 a second: 141,816)' % ('all work', work / ticks))
    return C, ticks
table(F, 'whole loop in play')
# seconds (50-frame windows in play, within one stage), split by ticks in the second
win = []
for i in range(0, len(F) - 50, 50):
    w = F[i:i + 50]
    if w[0][2] != w[-1][2] or w[-1][0] - w[0][0] != 49: continue
    win.append((sum(x[3] for x in w), w))
win.sort(key=lambda t: t[0])
q = len(win) // 4
table([x for _, w in win[:q] for x in w], 'busiest quarter of seconds (fewest ticks)')
table([x for _, w in win[-q:] for x in w], 'quietest quarter of seconds')
