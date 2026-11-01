"""Check the renderer: when the cells have been drawn (before sprites), the
hidden screen must show, for every cell, its tile from the converted tile set
(page 7) as named in name_shadow.

usage: check_screen.py SECONDS [skip_seconds] [every_n_ticks]
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
every = int(sys.argv[3]) if len(sys.argv) > 3 else 1
m = Spectrum()
for f in range(int(skip * 50)): m.run_frame()
sim = m.sim; regs = m.regs; FR = 70908; B = m.mem.banks
end = regs[25] + int(secs * 50 * FR); P = syms['rf_cells']; ns = syms['name_shadow'] - 0x8000
ticks = bad = 0
while regs[25] < end:
    m.tr.keyboard = keys_default(regs[25] // FR)
    m.hook()                    # NEM_ALL=1: all weapons once play starts (emu.py)
    sim.trace(m.pc, P, 0, end, 1, None, None, None, None, None); m.pc = regs[24]
    if m.pc != P: break
    ticks += 1
    if ticks % every == 0:
        hi = B[2][syms['r_scr_hi'] - 0x8000]
        scr = B[5] if hi == 0x40 else B[7]
        wrong = []
        for c in range(768):
            t, l = c >> 8, c & 255; tid = B[2][ns + c]
            exp = [B[7][((0xDB + 9 * t + r) << 8) - 0xC000 + tid] for r in range(9)]
            got = [scr[(t * 8 + r) * 256 + l] for r in range(8)] + [scr[0x1800 + c]]
            if exp != got: wrong.append((c, tid, bytes(exp).hex(), bytes(got).hex()))
        if wrong:
            bad += 1
            if bad <= 5: print('t=%.2fs state=%d %d cells, e.g. %s' % ((regs[25] - m.t0) / FR / 50, m.k(0xE000), len(wrong), wrong[:3]))
    sim.trace(m.pc, -1, 0, regs[25] + 4, 1, None, None, None, None, None); m.pc = regs[24]
print('ticks', ticks, 'checked', ticks // every, 'wrong', bad)
