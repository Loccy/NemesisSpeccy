"""Frames between screen flips over a stretch of play, and ticks per second.
usage: pacing.py SECONDS [skip_seconds] [sna]"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, collections
sys.path.insert(0, NEM_ROOT + '/spec')
from emu import Spectrum
secs = float(sys.argv[1]); skip = float(sys.argv[2]) if len(sys.argv) > 2 else 20
m = Spectrum(sys.argv[3]) if len(sys.argv) > 3 else Spectrum()
for f in range(int(skip * 50)): m.run_frame()
last = m.tr.out7ffd & 8; since = 0; hist = collections.Counter(); t0 = m.k(0xE003); ticks = 0
for f in range(int(secs * 50)):
    m.run_frame(); since += 1
    c = m.k(0xE003); ticks += (c - t0) & 255; t0 = c
    s = m.tr.out7ffd & 8
    if s != last:
        if since > 10: print('  gap of %d frames ending at %.1fs (state %d)' % (since, skip + (f + 1) / 50.0, m.k(0xE000)))
        hist[since] += 1; since = 0; last = s
n = sum(hist.values())
play = {k: v for k, v in hist.items() if k <= 6}
prate = 50.0 * sum(play.values()) / max(1, sum(k * v for k, v in play.items()))
print('in play (flips <= 6 frames apart): %.2f flips/s' % prate)
print('ticks/s %.1f  flips/s %.1f  frames between flips: %s' % (ticks / secs, n / secs,
      ', '.join('%d: %.0f%%' % (k, 100.0 * v / n) for k, v in sorted(hist.items()))))
