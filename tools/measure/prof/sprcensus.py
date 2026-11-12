"""Sprites drawn over the first loop: rows with pixels, columns, shifts.  And cells drawn: blank tiles."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, os, time, collections, pickle
os.environ['NEM_ALL'] = '1'
sys.path.insert(0, (_NEM + '/spec'))
from emu import Spectrum, _syms, keys_default
SNA = (_NEM + '/spec/nemesis.sna'); sy = _syms(SNA[:-4] + '.sym')
MODE = sys.argv[1]; NF = int(sys.argv[2])
s = Spectrum(SNA); sim = s.sim; R = s.regs; tr = s.tr; FR = 70908
STOP = sy['draw_sprite16.cols'] if MODE == 'spr' else sy['draw_cells.srca']
b2 = s.mem.banks[2]
def rd(a):
    if a < 0x8000: return s.mem.banks[5][a - 0x4000]
    if a < 0xC000: return b2[a - 0x8000]
    return s.mem.banks[tr.out7ffd & 7][a - 0xC000]
SPX = sy['sp_x']; SPY = sy['sp_y']; DCT = sy['dc_third']
rows = collections.Counter(); pats = collections.Counter(); stats = collections.Counter(); bystage = collections.defaultdict(collections.Counter)
t = time.time()
for f in range(NF):
    s.hook(advance=True); tr.keyboard = keys_default(s.frame)
    end = s.t0 + (s.frame + 1) * FR
    while R[25] < end:
        sim.trace(s.pc, STOP, 0, end, 1, None, None, None, None, None); s.pc = R[24]
        if s.pc == STOP and R[25] < end:
            st = s.k(0xE061) if s.k(0xE000) == 5 else 0
            if MODE == 'spr':
                hl = R[7] | R[6] << 8                      # H=6? check below
                hl = (R[6] << 8) | R[7]
                p = [rd(hl + i) for i in range(32)]
                ne = [i for i in range(16) if p[i] | p[i + 16]]
                x = rd(SPX); y = rd(SPY)
                C = bystage[st]
                C['n'] += 1
                if not ne: C['emptypat'] += 1
                else:
                    first, last = ne[0], ne[-1]
                    C['rows_used'] += last - first + 1
                    C['rows_nonempty'] += len(ne)
                    lc = any(p[i] for i in range(16)); rc = any(p[i + 16] for i in range(16))
                    if not rc: C['right_empty'] += 1; C['right_empty_rows'] += last - first + 1
                    if not lc: C['left_empty'] += 1
                    sh = x & 7
                    C['shift%d' % sh] += 1
                    # width in pixels
                    orl = 0; orr = 0
                    for i in range(16): orl |= p[i]; orr |= p[i + 16]
                    w = (orl << 8) | orr
                    lo = 15 - (w.bit_length() - 1); hi = 15 - ((w & -w).bit_length() - 1)
                    C['width'] += hi - lo + 1
                    bytes_needed = ((sh + hi) >> 3) - ((sh + lo) >> 3) + 1
                    C['bytes%d' % bytes_needed] += 1
                    C['rowbytes'] += (last - first + 1) * bytes_needed
                    pats[(st, hl, )] += 1
            else:
                C = bystage[st]; C['cells'] += 1
                if R[7] == 0: C['blank'] += 1
                elif R[7] in (0xF6, 0xF7): C['star'] += 1
            sim.trace(s.pc, -1, 1, end, 1, None, None, None, None, None); s.pc = R[24]
    s.frame += 1
    if s.k(0xE000) == 5 and s.k(0xE061) == 1 and f > 80000: break
print('%.0f s, frames %d' % (time.time() - t, s.frame))
tot = collections.Counter()
for st in sorted(bystage):
    C = bystage[st]; tot.update(C)
    print('stage', st, dict(C))
print('all', dict(tot))
pickle.dump(dict(bystage={k: dict(v) for k, v in bystage.items()}, pats=dict(pats)), open('census_%s.pkl' % MODE, 'wb'))
