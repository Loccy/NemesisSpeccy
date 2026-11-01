"""Run original and relocated one game tick at a time (virtual-clock
interrupts); stop at the first unexplained Konami-RAM difference."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, time
sys.path.insert(0, NEM_ROOT + '/reloc')
from layoutsim import *

STACK = range(0x1080, 0x10F0)          # F080-F0EF: stack, not compared

def run(N, report=100):
    orig = Original(); orig.boot(); rel = Relocated(); rel.boot()
    mp = Mapper(rel.syms)
    for i in range(N):
        vclock_tick(orig)
        try:
            vclock_tick(rel)
        except Exception as e:
            print('tick', i, 'relocated:', type(e).__name__, e, 'PC=%04X page %d' % (rel.sim.registers[24], rel.mem.page)); return orig, rel, i
        a = orig.snapshot(); b = rel.snapshot()
        bad = [k for k in explain(a, b, mp) if k not in STACK]
        if bad:
            print('tick %d: %d unexplained bytes' % (i, len(bad)))
            print('  ' + ' '.join('%04X:%02X/%02X' % (0xE000 + k, a[k], b[k]) for k in bad[:48]))
            return orig, rel, i
        if report and i % report == 0 and (i % 500 == 0 or N < 1000):
            print('  tick %d ok  state %d  phase %d  distance %04X' % (i, a[0], a[0x61], a[0x63] | a[0x64] << 8), flush=True)
    print('all %d ticks match' % N)
    return orig, rel, N

if __name__ == '__main__':
    t = time.time(); run(int(sys.argv[1]) if len(sys.argv) > 1 else 300); print('%.1fs' % (time.time() - t))
