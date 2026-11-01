"""Cost of Konami's tick alone (no interrupts) on the Spectrum build, versus the
same ticks in the MSX simulation."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re, os
sys.path.insert(0, NEM_ROOT + '/spec')
from emu import Spectrum, keys_default
syms = {}
for l in open(NEM_ROOT + '/spec/nemesis.sym'):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
m = Spectrum(); FR = 70908
for f in range(int(float(sys.argv[1]) * 50)): m.run_frame()
L0 = syms['pm_tick']; sim = m.sim; regs = m.regs
v = []; isr = []
for n in range(280):
    sim.trace(m.pc, L0, 0, regs[25] + 20 * FR, 1, None, None, None, None, None); m.pc = regs[24]
    t = regs[25]
    sim.trace(m.pc, L0 + 3, 0, regs[25] + 20 * FR, 0, None, None, None, None, None); m.pc = regs[24]   # no interrupts
    v.append(regs[25] - t)
# ISR cost: run the ISR body once from its entry with interrupts off
a = syms['isr']
v.sort(); print('Konami tick without interrupts: median %d p90 %d max %d' % (v[len(v) // 2], v[int(len(v) * .9)], v[-1]))
