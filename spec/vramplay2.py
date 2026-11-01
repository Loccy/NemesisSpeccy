import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, collections
sys.path.insert(0, NEM_ROOT + '/reloc'); sys.path.insert(0, NEM_ROOT + '/msxsim')
from layoutsim import Original, vclock_tick
N = int(sys.argv[1])
m = Original(); m.boot(); prev = bytes(m.vdp.vram)
runs = []
for t in range(N):
    vclock_tick(m); v = bytes(m.vdp.vram)
    if m.mem[0xE000] == 5 and v != prev:
        d = [i for i in range(0x3800) if v[i] != prev[i]]
        if d: runs.append((t, m.mem[0xE061], m.mem[0xE063] | m.mem[0xE064] << 8, len(d), sorted(set(i & 0xFFF8 for i in d))[:6]))
    prev = v
# print compressed: group consecutive ticks
for r in runs[:40]: print(r[0], 'ph', r[1], 'dist %04X' % r[2], 'n', r[3], ' '.join('%04X' % a for a in r[4]))
print('ticks with pattern/colour writes in play:', len(runs))
