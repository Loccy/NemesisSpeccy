import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, collections
sys.path.insert(0, NEM_ROOT + '/reloc'); sys.path.insert(0, NEM_ROOT + '/msxsim')
from layoutsim import Original, vclock_tick
N = int(sys.argv[1])
m = Original(); m.boot(); prev = bytes(m.vdp.vram)
chars = collections.Counter(); bigloads = []
for t in range(N):
    vclock_tick(m); v = bytes(m.vdp.vram)
    if m.mem[0xE000] == 5 and v != prev:
        d = [i for i in range(0x3800) if v[i] != prev[i]]
        if len(d) > 64: bigloads.append((t, m.mem[0xE061], len(d)))
        else:
            for i in d:
                tbl = 'col' if i < 0x1800 else 'spr' if i < 0x2000 else 'pat'
                o = i if i < 0x1800 else i - 0x1800 if i < 0x2000 else i - 0x2000
                chars[(tbl, o // 0x800 if tbl != 'spr' else 0, (o & 0x7FF) // 8)] += 1
    prev = v
print('big loads', bigloads)
for k, n in sorted(chars.items()): print(k[0], 'third', k[1], 'char %02X' % k[2], n)
