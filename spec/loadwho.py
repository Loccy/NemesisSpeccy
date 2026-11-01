import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, collections
sys.path.insert(0, NEM_ROOT + '/reloc'); sys.path.insert(0, NEM_ROOT + '/msxsim')
from layoutsim import Original, vclock_tick
from divtrace import conv_orig
ticks = [int(x) for x in sys.argv[1].split(',')]
m = Original(); m.boot()
# record call-ish trace (orig addresses) for big-load ticks; report the code items executed that are CALL targets from un_cuadro / state machine
t = 0
for T in ticks:
    while t < T: vclock_tick(m); t += 1
    rec = []
    vclock_tick(m, rec, conv_orig); t += 1
    seen = collections.Counter(x[0] for x in rec)
    # entry points: items in bank 0 42xx-44xx/49xx and callers
    print('tick', T, 'phase', m.mem[0xE061], 'steps', len(rec))
    order = []
    for x in rec:
        if x[0] not in order: order.append(x[0])
    print('  first-visit order (bank0 loaders):', ' '.join('%d:%04X' % a for a in order if a[0] == 0 and (0x4200 <= a[1] < 0x4460 or 0x4B00 <= a[1] < 0x4B40 or 0x53D0 <= a[1] < 0x5440))[:600])
