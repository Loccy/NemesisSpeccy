"""Konami's far calls on the 128K (10 November 2026): every entry to far_go
in play, by target, with whether it had to switch the page.  Shipped build,
all weapons (NEM_ALL=1), fire on keys_default's rhythm.
usage: farcount.py SNA SYM FRAMES"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, collections
sys.path.insert(0, (_NEM + '/spec'))
from emu import Spectrum, _syms, keys_default
s = Spectrum(sys.argv[1]); sy = _syms(sys.argv[2])
s.mem.banks[0][sy['m1_75F0'] - 0xC000] = 0xC9
sim = s.sim; R = s.regs; tr = s.tr; FR = 70908; FG = sy['far_go']; CP = sy['cur_page']
inv = {}
for k, v in sy.items():
    if '.' not in k: inv.setdefault(v, k)
def rd(a):
    if a < 0x4000: return 0
    if a < 0x8000: return s.mem.banks[5][a - 0x4000]
    if a < 0xC000: return s.mem.banks[2][a - 0x8000]
    return s.mem.banks[tr.out7ffd & 7][a - 0xC000]
def rw(a): return rd(a) | rd(a + 1) << 8
calls = collections.Counter(); sw = collections.Counter(); ticks0 = None; play = 0
for f in range(int(sys.argv[3])):
    kb = keys_default(f); s.hook(advance=True); tr.keyboard = kb
    end = s.t0 + (f + 1) * FR
    inplay = s.k(0xE000) == 5
    while R[25] < end:
        sim.trace(s.pc, FG, 0, end, 1, None, None, None, None, None); s.pc = R[24]
        if s.pc == FG:
            if inplay:
                stub = rw(R[12])             # the stub's data: page, target
                tgt = (rd(stub), rw(stub + 1))
                calls[tgt] += 1
                if rd(CP) != rd(stub): sw[tgt] += 1
            sim.trace(s.pc, -1, 1, end, 1, None, None, None, None, None); s.pc = R[24]
    s.frame = f + 1
    if inplay: play += 1
print('frames in play', play)
tot = sum(calls.values()); tsw = sum(sw.values())
print('far calls %d (%.1f a frame), switching %d (%.1f a frame)' % (tot, tot / play, tsw, tsw / play))
addrs = sorted(inv)
import bisect
def size(a):
    i = bisect.bisect_right(addrs, a)
    return (addrs[i] - a) if i < len(addrs) else None
cum = 0
for (pg, t), n in sw.most_common(25):
    cum += n
    print('%-22s page %d  %6d switching calls (%4.1f%%, cum %4.1f%%)  %5.2f a frame  ~%s bytes to next label' % (inv.get(t, '%04X' % t), pg, n, 100 * n / tsw, 100 * cum / tsw, n / play, size(t)))
