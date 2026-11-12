import sys, pickle, re, collections
D = pickle.load(open('loop.pkl', 'rb')); acc, cnt = D['acc'], D['cnt']
syms = {}
for l in open(D['sym']):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
ticks = cnt[syms['pm_tick']]
lo, hi = 0x5B00, syms['section_fixed_end']
print('bank 0 code %04X-%04X: %d bytes' % (lo, hi, hi - lo))
# label -> msx address
m0 = sorted((v, k) for k, v in syms.items() if re.match(r'm0_[0-9A-F]{4}$', k) and lo <= v < hi)
tot = sum(t for k, t in acc.items() if lo <= k < hi)
print('time in it: %d T/tick' % (tot / ticks))
# contiguous executed runs: group items into blocks separated by gaps of unexecuted items >= 24 bytes
items = []
for i, (a, k) in enumerate(m0):
    nxt = m0[i + 1][0] if i + 1 < len(m0) else hi
    items.append((a, nxt - a, sum(acc.get(x, 0) for x in range(a, nxt)), k))
# blocks of 32 bytes by density
B = 32; blocks = collections.Counter()
for a, n, t, k in items: blocks[(a - lo) // B] += t
order = sorted(blocks.items(), key=lambda x: -x[1]); cum = 0
marks = {512: None, 1024: None, 1536: None, 2048: None, 3072: None, 4096: None}
for i, (b, t) in enumerate(order):
    cum += t
    size = (i + 1) * B
    if size in marks: marks[size] = cum
for sz in sorted(marks): print('hottest %4d bytes (in %d-byte blocks): %5.1f%% of bank 0 time, %d T/tick' % (sz, B, 100 * marks[sz] / tot, marks[sz] / ticks))
# routines: runs of items with t>0, merged across gaps < 12 bytes
runs = []; cur = None
for a, n, t, k in items:
    if t > 0:
        if cur and a - (cur[0] + cur[1]) < 12: cur[1] = a + n - cur[0]; cur[2] += t
        else:
            cur = [a, n, t, k]; runs.append(cur)
runs.sort(key=lambda r: -r[2] / max(r[1], 1))
print('\nexecuted runs by T per byte:')
cb = 0; ct = 0
for a, n, t, k in sorted(runs, key=lambda r: -r[2])[:40]:
    print('  %s (%04X) %4d bytes %6d T/tick' % (k, a, n, t / ticks))
print('\ncumulative by density:')
for a, n, t, k in runs:
    cb += n; ct += t
    if t / ticks > 30: print('  %-8s %4d bytes %6d T/tick   cum %5d bytes %5.1f%%' % (k, n, t / ticks, cb, 100 * ct / tot))
