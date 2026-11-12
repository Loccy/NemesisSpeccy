import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, json, collections
sys.path.insert(0, (_NEM + '/spec'))
import emu
from emu import Spectrum
SNA, SYM = sys.argv[1], sys.argv[2]
WIN = {'quiet': (15, 25), 'hatch': (108, 116), 'volcano': (140, 150), 'boss': (175, 183)}
s = Spectrum(SNA); sy = emu._syms(SYM); regs = s.regs; FR = 70908
s.mem.banks[0][sy['m1_75F0'] - 0xC000] = 0xC9
def keys(f):
    kb = [0] * 8
    fire = ((f // 25) % 4 == 0) if s.k(0xE000) != 5 else ((f // 2) % 8 < 4)
    if fire: kb[7] |= 1
    return kb
def rd(a): return s.mem[a]
stops = [sy['erase_sprites'], sy['rf_erased'], sy['rf_sprites']]
D0 = sy['dirty0']
NS = sy['name_shadow']; seen = {0: {}, 0x80: {}}
def same_count():
    h = rd(sy['r_dirty']); base = D0 + h; n = 0; tot = 0
    for i in range(96):
        b = rd(base + i)
        for bit in range(8):
            if b >> bit & 1:
                cell = (i >> 5) * 256 + (i & 31) * 8 + bit
                tid = rd(NS + cell); tot += 1
                if seen[h].get(cell) == tid: n += 1
                seen[h][cell] = tid
    return n
def pop():
    base = D0 + (rd(sy['r_dirty']))
    return sum(bin(rd(base + i)).count('1') for i in range(96))
def nrec():
    a = rd(sy['r_erase']) | rd(sy['r_erase'] + 1) << 8
    n = 0
    while rd(a + 4 * n) != 0xff: n += 1
    return n
st = {w: collections.Counter() for w in WIN}; last = s.k(0xE003); played = 0
while played < 184 * 50:
    w = next((n for n, (a, b) in WIN.items() if a * 50 <= played < b * 50), None) if s.k(0xE000) == 5 else None
    if w is None:
        s.run_frame(keys)
    else:
        s.hook(advance=True); s.tr.keyboard = keys(s.frame)
        end = s.t0 + (s.frame + 1) * FR; pc = s.pc; k = 0
        while regs[25] < end:
            s.sim.trace(pc, stops[k], 0, end, 1, None, None, None, None, None)
            pc = regs[24]
            if pc == stops[k]:
                if k == 0: st[w]['names'] += pop(); st[w]['screens'] += 1; st[w]['same'] += same_count()
                elif k == 1: st[w]['cells'] += pop()
                else: st[w]['sprites'] += nrec()
                k = (k + 1) % 3
        s.pc = pc; s.frame += 1
    c = s.k(0xE003)
    if w: st[w]['ticks'] += (c - last) & 255
    last = c
    if s.k(0xE000) == 5: played += 1
for w in WIN:
    c = st[w]; n = max(c['screens'], 1)
    print('%-8s ticks %d screens %d | per screen: cells drawn %.0f (before erase %.0f, added by erase %.0f), sprites %.1f, name-dirty cells whose tile number this screen already showed %.0f' % (w, c['ticks'], n, c['cells'] / n, c['names'] / n, (c['cells'] - c['names']) / n, c['sprites'] / n, c['same'] / n))
