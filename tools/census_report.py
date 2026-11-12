import sys, json, collections
L = json.load(open(sys.argv[1]))
SEC_T = 70908 * 50
L = [x for x in L if x[1] > 0 or x[2] != 0]          # drop the title screen
print('conversions %d, distinct inputs %d, conversion time %.1f s of CPU' % (len(L), len({x[0] for x in L}), sum(x[3] for x in L) / SEC_T))
# stage spans
first = {}
for inp, t, st, T in L: first.setdefault(st, t)
seen = set(); print('\nstage  from(s)  conversions  distinct  new  CPU(s)')
by = collections.defaultdict(list)
for x in L: by[x[2]].append(x)
for st in sorted(by, key=lambda k: first[k]):
    xs = by[st]; d = {x[0] for x in xs}; new = d - seen; seen |= d
    print('%5d  %7.0f  %11d  %8d  %4d  %6.1f' % (st, first[st], len(xs), len(d), len(new), sum(x[3] for x in xs) / SEC_T))
# worst seconds
sec = collections.defaultdict(list)
for x in L: sec[int(x[1])].append(x)
worst = sorted(sec, key=lambda s: -sum(x[3] for x in sec[s]))
print('\nworst seconds (share of that second\'s CPU spent converting):')
for s_ in worst[:20]:
    xs = sec[s_]; print('  second %5d stage %2d (%4.0f s into it): %3d conversions, %3d distinct, %4.1f%%' % (s_, xs[0][2], s_ - first[xs[0][2]], len(xs), len({x[0] for x in xs}), 100 * sum(x[3] for x in xs) / SEC_T))
heavy = [s_ for s_ in sec if sum(x[3] for x in sec[s_]) > 0.2 * SEC_T]
print('\nseconds with over 20%% of the CPU converting: %d (by stage %s)' % (len(heavy), dict(collections.Counter(sec[s_][0][2] for s_ in heavy))))
# value of a build-time table: inputs ranked by total time they cost
cost = collections.Counter(); 
for inp, t, st, T in L: cost[inp] += T
tot = sum(cost.values()); acc = 0
print('\nprebuilt table, inputs ranked by total conversion time saved (25 bytes an entry):')
marks = [25, 50, 76, 100, 150, 200, 300, 500, 1000, len(cost)]
for i, (inp, c) in enumerate(cost.most_common(), 1):
    acc += c
    if i in marks:
        top = {k for k, _ in cost.most_common(i)}
        hv = sum(1 for s_ in sec if sum(x[3] for x in sec[s_] if x[0] not in top) > 0.2 * SEC_T)
        print('  %5d entries %6d bytes: %5.1f%% of conversion time, seconds still over 20%%: %d' % (i, 25 * i, 100 * acc / tot, hv))
