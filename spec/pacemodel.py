"""Pacing model over logged per-tick costs (pacelog.py).  Two screens: a
tick's drawing starts only once the previous screen is showing; the next
tick's logic starts when drawing ends; flips happen at frame starts.
usage: pacemodel.py LOG.json [real]   ('real': sound in the interrupt, 3.4k a
frame, instead of once per tick in the logic as in the test build)"""
import sys, json, math, collections
FR = 70908
rows = [r for r in json.load(open(sys.argv[1]))[300:] if r[3]]
REAL = len(sys.argv) > 2 and sys.argv[2] == 'real'
ISR = 3400 if REAL else 0
SND = 3400 if REAL else 0          # taken back out of the logic: the test build ran it once a tick there
def adv(t, w):
    while w > 0:
        nb = (t // FR + 1) * FR
        if t + w <= nb: return t + w
        w -= nb - t; t = nb + ISR
    return t
def ceilf(t): return -(-t // FR) * FR
def model(rule, cap=1):
    flip = 0; rd = 0; target = 0; flips = []; skipped = 0; carry = 0; lastskip = False
    for L, R, s, p, f in rows:
        L = max(L - SND, 0); R = R + carry; carry = 0
        target += 2 * FR
        ld = adv(rd, L)
        if rule == 'skip' and not lastskip and ld + R > target + FR:
            skipped += 1; lastskip = True; carry = R // 2; rd = ld
            continue
        lastskip = False
        rs = max(ld, flip); rdn = adv(rs, R)
        if rule == 'current': due = flip + 2 * FR
        elif rule == 'catchup': due = max(flip + FR, target)
        else: due = flip + 2 * FR
        nf = ceilf(max(rdn, due))
        flips.append((nf - flip) // FR); flip = nf; rd = rdn
        if rule in ('catchup', 'skip') and flip - target > cap * FR: target = flip - cap * FR
    secs = flip / FR / 50.0
    h = collections.Counter(min(g, 6) for g in flips[1:])
    n = sum(h.values())
    return len(rows) / secs, len(flips) / secs, h, n, skipped
def show(name, r):
    tps, fps, h, n, sk = r
    print('  %-22s ticks/s %5.2f  shown/s %5.2f  gaps %s%s' % (name, tps, fps,
          ' '.join('%d:%d%%' % (k, round(100 * v / n)) for k, v in sorted(h.items())),
          '  skipped %d%%' % round(100 * sk / len(rows)) if sk else ''))
if not REAL:
    fr = [r[4] for r in rows]; g = collections.Counter(min(b - a, 6) for a, b in zip(fr, fr[1:]))
    n = sum(g.values())
    print('  %-22s ticks/s %5.2f  gaps %s' % ('actual test build', 50.0 * len(fr) / (fr[-1] - fr[0]),
          ' '.join('%d:%d%%' % (k, round(100 * v / n)) for k, v in sorted(g.items()))))
show('current', model('current'))
show('catch-up, cap 1 frame', model('catchup', 1))
show('catch-up, cap 2 frames', model('catchup', 2))
show('skip (never twice)', model('skip', 2))
