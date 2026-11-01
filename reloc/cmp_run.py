import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, time
sys.path.insert(0, NEM_ROOT + '/reloc')
from layoutsim import *
N = int(sys.argv[1]) if len(sys.argv) > 1 else 300
orig = Original(); orig.boot(); A = []
t = time.time(); run_ticks(orig, N, lambda i, m: A.append(m.snapshot()))
print('original %d ticks, %d frames, %.1fs' % (len(A), orig.frames, time.time() - t))
rel = Relocated(); rel.boot(); B = []
t = time.time()
try:
    run_ticks(rel, N, lambda i, m: B.append(m.snapshot()))
except Exception as e:
    print('relocated stopped:', type(e).__name__, e, 'PC=%04X page=%d' % (rel.sim.registers[24], rel.mem.page))
print('relocated %d ticks, %d frames, %.1fs' % (len(B), rel.frames, time.time() - t))
mp = Mapper(rel.syms)
for i, (a, b) in enumerate(zip(A, B)):
    bad = explain(a, b, mp)
    if bad:
        print('first unexplained difference at tick', i, '(%d bytes):' % len(bad))
        print('  ' + ' '.join('E%03X:%02X/%02X' % (k, a[k], b[k]) for k in bad[:40]))
        break
else:
    print('all', min(len(A), len(B)), 'ticks match (relocation-aware)')
