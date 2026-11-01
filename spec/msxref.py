"""Render the MSX original (simulated) at given distances, for comparison."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys
sys.path.insert(0, NEM_ROOT + '/reloc'); sys.path.insert(0, NEM_ROOT + '/msxsim')
from layoutsim import Original, vclock_tick
from screen import render
targets = [int(x, 16) for x in sys.argv[1].split(',')]
m = Original(); m.boot(); t = 0
for d in targets:
    while (m.mem[0xE063] | m.mem[0xE064] << 8) < d or m.mem[0xE000] != 5:
        vclock_tick(m); t += 1
    render(m.vdp, NEM_ROOT + '/spec/shots/msx_%04X.png' % d)
    print('dist %04X at tick %d' % (d, t))
