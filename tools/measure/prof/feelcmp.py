import json, sys
names = sys.argv[1::2]; files = sys.argv[2::2]
D = [json.load(open(f)) for f in files]
print('game stage | ticks/s ' + ' '.join('%7s' % n for n in names) + ' | pictures/s ' + ' '.join('%7s' % n for n in names) + ' | worst second')
T = [[0, 0, 0] for _ in D]
for k in sorted(D[0]['stages'], key=int):
    xs = [d['stages'][k] for d in D]
    print('%10s |         ' % k + ' '.join('%7.2f' % x['ticks_per_s'] for x in xs) + ' |            ' + ' '.join('%7.2f' % x['screens_per_s'] for x in xs) + ' | ' + ' '.join(str(x['worst_s']) for x in xs))
    for t, x in zip(T, xs):
        t[0] += x['seconds']; t[1] += x['ticks_per_s'] * x['seconds']; t[2] += x['screens_per_s'] * x['seconds']
print('loop ticks/s    ' + ' '.join('%7.2f' % (t[1] / t[0]) for t in T) + '   last on first %+.1f%%, on the one before %+.1f%%' % (100 * (T[-1][1] / T[-1][0] / (T[0][1] / T[0][0]) - 1), 100 * (T[-1][1] / T[-1][0] / (T[-2][1] / T[-2][0]) - 1)))
print('loop pictures/s ' + ' '.join('%7.2f' % (t[2] / t[0]) for t in T) + '   last on first %+.1f%%, on the one before %+.1f%%' % (100 * (T[-1][2] / T[-1][0] / (T[0][2] / T[0][0]) - 1), 100 * (T[-1][2] / T[-1][0] / (T[-2][2] / T[-2][0]) - 1)))
