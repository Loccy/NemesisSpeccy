"""Which VRAM regions does the original change during play (state 5)?"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, collections
sys.path.insert(0, NEM_ROOT + '/reloc'); sys.path.insert(0, NEM_ROOT + '/msxsim')
from layoutsim import Original, vclock_tick
N = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
m = Original(); m.boot()
reg = collections.Counter(); addrs = collections.defaultdict(collections.Counter)
prev = bytes(m.vdp.vram); phases = {}
for t in range(N):
    vclock_tick(m)
    v = bytes(m.vdp.vram); st = m.mem[0xE000]; ph = m.mem[0xE061]
    if v != prev:
        for i in range(0x4000):
            if v[i] != prev[i]:
                r = ('col' if i < 0x1800 else 'spr?' if i < 0x2000 else 'pat' if i < 0x3800 else 'name/attr')
                reg[(st, ph, r)] += 1; addrs[(st, ph, r)][i & 0xFFC0] += 1
    prev = v
    if t % 1000 == 0: print(t, 'state', st, 'phase', ph, 'regs', ' '.join('%02X' % x for x in m.vdp.reg), flush=True)
for k, n in sorted(reg.items()):
    print(k, n, ' '.join('%04X:%d' % kv for kv in sorted(addrs[k].items())[:12]))
