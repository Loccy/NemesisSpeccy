"""Check the trimmed boxes: for every sprite drawn, every cell whose bitmap
or attribute draw_sprite16 changed lies inside the record it wrote (which
the next erase uses); count cells saved against the full box."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys
sys.path.insert(0, (_SCRATCH + '/bis_t/spec')); os.environ['NEM_ALL'] = '1'
from emu import Spectrum, _syms, keys_default
s = Spectrum((_SCRATCH + '/night2/trim/trim.sna')); sy = _syms((_SCRATCH + '/night2/trim/trim.sym'))
s.mem.banks[0][sy['m1_75F0'] - 0xC000] = 0xC9
sim = s.sim; R = s.regs; tr = s.tr; FR = 70908
DS = sy['draw_sprite16']; B2 = s.mem.banks[2]
def fx(a): return B2[a - 0x8000]
def cell_addr(cx, cy, l):
    y = cy * 8 + l; return ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | cx
n = bad = empty = 0; full = kept = 0; stages = set()
SECS = float(sys.argv[1])
for f in range(int(SECS * 50)):
    s.hook(advance=True); kb = keys_default(f); ph = f % 400
    if ph < 100: kb[5] |= 1
    elif ph < 200: kb[5] |= 2
    elif ph < 300: kb[2] |= 1
    else: kb[1] |= 1
    tr.keyboard = kb
    end = s.t0 + (f + 1) * FR
    while R[25] < end:
        sim.trace(s.pc, DS, 0, end, 1, None, None, None, None, None); s.pc = R[24]
        if s.pc != DS: break
        sp = R[12]; ret = B2[sp - 0x8000] | B2[sp + 1 - 0x8000] << 8
        bank = s.mem.banks[5] if fx(sy['r_scr_hi']) == 0x40 else s.mem.banks[7]
        pre = bytes(bank[0:6912]); ep0 = fx(sy['r_eptr']) | fx(sy['r_eptr'] + 1) << 8
        x, y = fx(sy['sp_x']), fx(sy['sp_y'])
        fullbox = (3 if x & 7 else 2) * (3 if y & 7 else 2)
        sim.trace(s.pc, ret, 0, end + 4 * FR, 1, None, None, None, None, None); s.pc = R[24]
        post = bytes(bank[0:6912]); ep1 = fx(sy['r_eptr']) | fx(sy['r_eptr'] + 1) << 8
        changed = set()
        for cy in range(24):
            for cx in range(32):
                if pre[6144 + cy * 32 + cx] != post[6144 + cy * 32 + cx] or any(pre[cell_addr(cx, cy, l)] != post[cell_addr(cx, cy, l)] for l in range(8)):
                    changed.add((cx, cy))
        n += 1; stages.add(s.k(0xE061)); full += fullbox
        if ep1 == ep0:
            empty += 1; bad += bool(changed); continue
        rx, ry, rc, rr = fx(ep0), fx(ep0 + 1), fx(ep0 + 2), fx(ep0 + 3)
        rect = set((rx + i, ry + j) for i in range(rc) for j in range(rr))
        kept += len(rect)
        if not changed <= rect:
            bad += 1
            if bad <= 5: print('outside', f, x, y, sorted(changed - rect), (rx, ry, rc, rr), flush=True)
    s.frame = f + 1
    if f % 5000 == 0: print(f, n, bad, flush=True)
    if s.k(0xE061) == 1 and 8 in stages and s.k(0xE000) == 5: break
print('sprites checked', n, 'outside the record', bad, 'empty', empty, 'stages', sorted(stages), 'box cells %.2f -> %.2f a sprite' % (full / max(n, 1), kept / max(n - empty, 1)))
