import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys
sys.path.insert(0, NEM_ROOT + '/reloc'); sys.path.insert(0, NEM_ROOT + '/msxsim')
from layoutsim import Original, vclock_tick
from divtrace import conv_orig
T = int(sys.argv[1])
m = Original(); m.boot()
for t in range(T): vclock_tick(m)
rec = []; vclock_tick(m, rec, conv_orig)
i = [k for k, x in enumerate(rec) if x[0] == (0, 0x4371)][0]
for x in rec[i - 25:i + 1]: print('%d:%04X A=%02X HL=%04X DE=%04X' % (x[0] + x[1:4]))
