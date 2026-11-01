"""Run both to tick t, then log writes to one Konami RAM address during tick t."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys
sys.path.insert(0, NEM_ROOT + '/reloc')
from layoutsim import *
from divtrace import reverse_map, GEN
t = int(sys.argv[1]); addr = int(sys.argv[2], 16)
orig = Original(); orig.boot(); rel = Relocated(); rel.boot()
for i in range(t): vclock_tick(orig); vclock_tick(rel)
rv = reverse_map(rel.syms)
def hook(m, a0, name, conv):
    M = m.mem; Base = type(M); log = []
    class W(Base):
        def __setitem__(self, a, v):
            if a == a0: log.append((conv(m.sim.registers[24]), v, m.sim.registers[0]))
            Base.__setitem__(self, a, v)
    M.__class__ = W
    return log
co = lambda pc: '%d:%04X' % ((0 if pc < 0x6000 else orig.mem.bank[(pc - 0x4000) >> 13]), pc) if 0x4000 <= pc < 0xC000 else '%04X' % pc
cr = lambda pc: ' '.join('%d:%04X' % x for x in rv.get(pc, [])) or '%04X' % pc
la = hook(orig, addr, 'orig', co); lb = hook(rel, addr + RAM_DELTA, 'rel', cr)
vclock_tick(orig); vclock_tick(rel)
print('original:', la); print('relocated:', lb)
