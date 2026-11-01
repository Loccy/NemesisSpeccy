"""Statistical profile of the Spectrum build: sample the PC every few hundred
T-states during play and attribute samples to the nearest label.

usage: sample_prof.py SECONDS [skip_seconds] [slice_T]
"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re, os, bisect, collections
sys.path.insert(0, NEM_ROOT + '/spec')
from emu import Spectrum, keys_default
HERE = NEM_ROOT + '/spec'
syms = {}
for l in open(os.path.join(HERE, 'nemesis.sym')):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
# Konami items: group by MSX routine name from the listing labels where possible
fixed = sorted((v, k) for k, v in syms.items() if v < 0xC000 and not k.startswith('m') or (v < 0xC000 and k.startswith('m0_')))
paged = collections.defaultdict(list)
PN = {'A': 0, 'B': 3, 'C': 4, 'D': 6, 'E': 1}
sys.path.insert(0, NEM_ROOT + '/reloc')
import gen as G
os.environ['NEM_TARGET'] = 'spec'
g = G.Gen(open(NEM_ROOT + '/nem.rom', 'rb').read())
for k, v in syms.items():
    mm = re.match(r'(?:([A-Z])_)?m(\d+)_([0-9A-F]{4})$', k)
    if mm and v >= 0xC000:
        b = int(mm.group(2)); a = int(mm.group(3), 16)
        sec = mm.group(1) or g.home.get((b, a))
        if sec in PN: paged[PN[sec]].append((v, k))
for p in paged: paged[p].sort()
fk = [v for v, k in fixed]
# MSX routine names from the listing: label -> address, per bank
names = {}
for b in (0, 1, 2, 3, 7):
    _, labels, _ = __import__('listing').parse(b, open(NEM_ROOT + '/nem.rom', 'rb').read())
    for n, a in labels.items():
        if a is not None and not n.startswith(('L_', 'DATA_')): names.setdefault(b, []).append((a, n))
for b in names: names[b].sort()
def msx_name(label):
    mm = re.match(r'(?:[A-Z]_)?m(\d+)_([0-9A-F]{4})', label)
    if not mm: return label
    b = int(mm.group(1)); a = int(mm.group(2), 16)
    L = names.get(b, [])
    i = bisect.bisect_right(L, (a, '~')) - 1
    return '%d:%s' % (b, L[i][1]) if i >= 0 else label
def where(pc, page):
    if pc < 0xC000:
        i = bisect.bisect_right(fk, pc) - 1
        return msx_name(fixed[i][1]) if i >= 0 else '?'
    L = paged.get(page, [])
    i = bisect.bisect_right([v for v, k in L], pc) - 1
    return msx_name(L[i][1]) if i >= 0 else 'page%d?' % page
secs = float(sys.argv[1]); skip = float(sys.argv[2]) if len(sys.argv) > 2 else 0
SL = int(sys.argv[3]) if len(sys.argv) > 3 else 397
m = Spectrum()
for f in range(int(skip * 50)): m.run_frame()
sim = m.sim; regs = m.regs; FR = 70908
end = regs[25] + int(secs * 50 * FR)
hist = collections.Counter(); n = 0
PHASE = os.environ.get('PHASE')          # 'tick': only sample inside Konami's tick
a0, a1 = {'tick': (syms['pm_tick'], syms['pm_tiles']), 'tiles': (syms['pm_tiles'], syms['pm_render']),
          'cells': (syms['rf_erased'], syms['rf_cells']), 'sprites': (syms['rf_cells'], syms['rf_sprites'])}.get(PHASE, (0, 0))
while regs[25] < end:
    m.tr.keyboard = keys_default(regs[25] // FR)
    if PHASE in ('tick', 'tiles', 'cells', 'sprites'):
        sim.trace(m.pc, a0, 0, end, 1, None, None, None, None, None); m.pc = regs[24]
        while regs[25] < end:
            sim.trace(m.pc, a1, 0, regs[25] + SL, 1, None, None, None, None, None); m.pc = regs[24]
            if m.pc == a1: break
            hist[where(m.pc, m.tr.out7ffd & 7)] += 1; n += 1
        continue
    sim.trace(m.pc, -1, 0, regs[25] + SL, 1, None, None, None, None, None); m.pc = regs[24]
    hist[where(m.pc, m.tr.out7ffd & 7)] += 1; n += 1
tot = sum(hist.values())
for k, v in hist.most_common(int(os.environ.get("TOP","45"))):
    print('%5.1f%%  %s' % (100.0 * v / tot, k))
