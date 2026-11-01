"""Check the map-buffer write tracking: after each Konami tick, the buffer
(BC00-BEBF) must equal name_shadow unless a full comparison is pending or the cell is in nm_list.

usage: check_names.py SECONDS [skip_seconds]
"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re, os
sys.path.insert(0, NEM_ROOT + '/spec')
from emu import Spectrum, keys_default
HERE = NEM_ROOT + '/spec'
syms = {}
for l in open(os.path.join(HERE, 'nemesis.sym')):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
secs = float(sys.argv[1]); skip = float(sys.argv[2]) if len(sys.argv) > 2 else 0
m = Spectrum()
for f in range(int(skip * 50)): m.run_frame()
sim = m.sim; regs = m.regs; FR = 70908; b2 = m.mem.banks[2]
end = regs[25] + int(secs * 50 * FR); P = syms['pm_tiles']; ns = syms['name_shadow'] - 0x8000
nf = syms['nm_full'] - 0x8000; ticks = bad = 0
while regs[25] < end:
    m.tr.keyboard = keys_default(regs[25] // FR)
    m.hook()                    # NEM_ALL=1: all weapons once play starts (emu.py)
    sim.trace(m.pc, P, 0, end, 1, None, None, None, None, None); m.pc = regs[24]
    if m.pc != P: break
    ticks += 1
    if not b2[nf]:
        np = b2[syms['nm_ptr'] - 0x8000] | b2[syms['nm_ptr'] - 0x7FFF] << 8
        nl = syms['nm_list']
        pend = set()
        for a in range(nl, np, 4):
            e = a - 0x8000; c0 = (b2[e] | b2[e + 1] << 8) - 0xBC00
            for r in range(b2[e + 3]):
                for x in range(b2[e + 2]): pend.add(c0 + 32 * r + x)
        np2 = b2[syms['nm2_ptr'] - 0x8000] | b2[syms['nm2_ptr'] - 0x7FFF] << 8
        for a in range(syms['nm2_list'], np2, 2):
            e = a - 0x8000; c0 = (b2[e] | b2[e + 1] << 8) - 0xBC00
            pend |= {c0, c0 + 1, c0 + 32, c0 + 33}
        d = [i for i in range(704) if b2[0x3C00 + i] != b2[ns + i] and i not in pend]
        if d:
            bad += 1
            if bad < 6: print('t=%.2fs T=%d state=%d cells %s' % ((regs[25]-m.t0) / FR / 50, regs[25], m.k(0xE000), [(i, b2[0x3C00+i], b2[ns+i]) for i in d[:6]]))
    sim.trace(m.pc, -1, 0, regs[25] + 4, 1, None, None, None, None, None); m.pc = regs[24]
print('ticks', ticks, 'mismatched', bad)
