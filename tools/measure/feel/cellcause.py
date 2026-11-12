"""Cells redrawn per drawn picture, by cause, and sprite boxes against the
cells their pixels touch (128K, 10 November 2026).

The shipped build in the Spectrum simulator through the first loop: the
ship invulnerable, Konami's all-weapons cheat (NEM_ALL=1), keys_default's
fire rhythm, no other keys.  For each picture render_frame draws:
  * at erase_sprites (entry): the hidden screen's dirty bitmap holds the
    cells marked since that screen was last drawn (map changes, the scroll);
  * after it (8B29): plus the cells under last time's sprites on that screen;
  * at rf_cells (draw_cells done) and rf_sprites (sprites drawn): the screen's
    bitmap and attributes before and after the sprites, and the erase list
    the sprites left (their boxes, [cx, cy, cols, rows]).
Content cells: cells inside the boxes whose bitmap bytes the sprites changed
(a sprite pixel over a pixel already set changes nothing, so this slightly
undercounts).
usage: cellcause.py SNA SYM SECONDS OUT.pkl"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, pickle, collections
sys.path.insert(0, os.environ.get('NEM_SPEC', (_NEM + '/spec')))
from emu import Spectrum, _syms, keys_default
SNA, SYM, SECS, OUT = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
s = Spectrum(SNA); sy = _syms(SYM)
s.mem.banks[0][sy['m1_75F0'] - 0xC000] = 0xC9
sim = s.sim; R = s.regs; tr = s.tr; FR = 70908
ES, AFTER, RFC, RFS = sy['erase_sprites'], 0x8B29, sy['rf_cells'], sy['rf_sprites']
assert sy['render_frame'] < AFTER < sy['rf_erased']
B2 = s.mem.banks[2]
def fx(a): return B2[a - 0x8000]
def dirty_cells(base):
    out = set()
    for cy in range(24):
        for b in range(4):
            v = fx(0xA000 + base + cy * 4 + b)
            for bit in range(8):
                if v >> bit & 1: out.add((b * 8 + bit, cy))
    return out
def scr_bank(): return s.mem.banks[5 if fx(sy['r_scr_hi']) == 0x40 else 7]
def snap():
    m = scr_bank(); return bytes(m[:6912])
def cell_addr(cx, cy, line):
    y = cy * 8 + line
    return ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | cx
SEQ = [ES, AFTER, RFC, RFS]
st = 0; pics = []; cur = {}
stage_start = {}; seen8 = False; ticks = 0; last3 = s.k(0xE003)
for f in range(int(SECS * 50)):
    in_play = s.k(0xE000) == 5
    s.hook(advance=True)
    tr.keyboard = keys_default(f)
    end = s.t0 + (f + 1) * FR
    while True:
        sim.trace(s.pc, SEQ[st], 0, end, 1, None, None, None, None, None); s.pc = R[24]
        if s.pc != SEQ[st] or R[25] >= end: break
        base = fx(sy['r_dirty'])
        if st == 0:
            cur = dict(f=f, stage=s.k(0xE061), play=int(s.k(0xE000) == 5), map=dirty_cells(base))
        elif st == 1:
            cur['after'] = dirty_cells(base)
        elif st == 2:
            cur['pre'] = snap()
        else:
            post = snap(); pre = cur.pop('pre')
            ea = fx(sy['r_erase']) | fx(sy['r_erase'] + 1) << 8
            boxes = []; a = ea
            while fx(a) != 0xFF and len(boxes) < 64:
                boxes.append((fx(a), fx(a + 1), fx(a + 2), fx(a + 3))); a += 4
            box = set()
            for cx, cy, c, r in boxes:
                for i in range(c):
                    for j in range(r):
                        if cy + j < 24 and cx + i < 32: box.add((cx + i, cy + j))
            touched = set(cell for cell in box if any(pre[cell_addr(cell[0], cell[1], l)] != post[cell_addr(cell[0], cell[1], l)] for l in range(8)))
            cur.update(boxes=boxes, box=len(box), boxsum=sum(min(c, 32 - cx) * max(0, min(r, 24 - cy)) for cx, cy, c, r in boxes),
                       touched=len(touched))
            m = cur['map']; aft = cur.pop('after')
            cur.update(map=len(m), erase_only=len(aft - m), erase_all=len(aft) - len(m) + len(m & (aft - m)), total=len(aft))
            pics.append(cur)
        st = (st + 1) % 4
        sim.trace(s.pc, -1, 1, end, 1, None, None, None, None, None); s.pc = R[24]   # past the stop
    s.frame = f + 1
    e = s.k(0xE003); ticks += (e - last3) & 255; last3 = e
    stg = s.k(0xE061)
    if in_play:
        if stg == 8: seen8 = True
        key = (2 if seen8 and stg != 8 else 1, stg)
        if key not in stage_start: stage_start[key] = (f, ticks)
        if key[0] == 2: break
    if f % 10000 == 0: print(f, len(pics), flush=True)
pickle.dump(dict(pics=pics, stage_start=stage_start), open(OUT, 'wb'))
print('done', len(pics))
