"""Exact T-states spent inside a routine (entry to its return), per tick.
usage: fncost.py ROUTINE SECONDS [skip]"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re
sys.path.insert(0, NEM_ROOT + '/spec')
from emu import Spectrum, keys_default
syms = {}
for l in open(NEM_ROOT + '/spec/nemesis.sym'):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
fn = syms[sys.argv[1]]; secs = float(sys.argv[2]); skip = float(sys.argv[3]) if len(sys.argv) > 3 else 20
m = Spectrum(); sim = m.sim; regs = m.regs; FR = 70908
for f in range(int(skip * 50)): m.run_frame()
end = regs[25] + int(secs * 50 * FR); tot = 0; calls = 0; t0 = m.k(0xE003); ticks = 0
while regs[25] < end:
    m.tr.keyboard = keys_default(regs[25] // FR)
    sim.trace(m.pc, fn, 0, end, 1, None, None, None, None, None); m.pc = regs[24]
    if m.pc != fn: break
    sp = regs[12]; ret = m.mem[sp] | m.mem[sp + 1] << 8; t = regs[25]
    # run until we return to ret with SP above the entry SP
    while True:
        sim.trace(m.pc, ret, 0, end, 1, None, None, None, None, None); m.pc = regs[24]
        if m.pc != ret or regs[12] > sp: break
        sim.trace(m.pc, -1, 1, end, 1, None, None, None, None, None); m.pc = regs[24]
    tot += regs[25] - t; calls += 1
c = m.k(0xE003); ticks = (c - t0) & 0xFF
print('%s: %d calls, %.0f T per call, %.0f T per second' % (sys.argv[1], calls, tot / max(1, calls), tot / secs))
