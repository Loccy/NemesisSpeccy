"""Check the sprites: after render_frame, the hidden screen must be the cells'
tiles with Konami's sprites (attribute buffer EC80, patterns at F800 page 7)
ORed in and their cells coloured, as draw_sprites defines it.

usage: check_sprites.py SECONDS [skip_seconds] [every_n_ticks]
MISSILE=1: give the ship the missile once play starts, fire held (and down
for the first 20 ticks), so that missiles roll along the ground (it reports
how many were checked over terrain: if none, the run has drifted).
EDGE=1: on each checked tick, sprites crossing the left and right edges (and
just inside them) are added to the end of Konami's list for that drawing
alone, sweeping every pixel position, so the clipping is checked whether or
not the game puts sprites there; the list is put back afterwards.
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
TRIM = 'sp_trim' in syms or 'sp_calc' in syms   # 1.1.2 on: boxes trimmed to the pixels (NEM_TRIM=0: whole boxes)
secs = float(sys.argv[1]); skip = float(sys.argv[2]) if len(sys.argv) > 2 else 0
every = int(sys.argv[3]) if len(sys.argv) > 3 else 1
m = Spectrum()
for f in range(int(skip * 50)): m.run_frame()
sim = m.sim; regs = m.regs; FR = 70908; B = m.mem.banks
def fx(a): return B[2][a - 0x8000]
spr_ink = [fx(syms['spr_ink'] + i) for i in range(16)]
end = regs[25] + int(secs * 50 * FR); P = syms['rf_sprites']; ns = syms['name_shadow']
ticks = bad = 0; nspr = 0; nedge = 0; nskip = 0
MISSILE = os.environ.get('MISSILE') == '1'; played = 0; nkeep = 0
EDGE = os.environ.get('EDGE') == '1'; DS = syms['draw_sprites']; SA = 0xEC80 + 0xAF00 - 0xE000 - 0x8000
while regs[25] < end:
    m.tr.keyboard = keys_default(regs[25] // FR)
    m.hook()                    # NEM_ALL=1: all weapons once play starts (emu.py)
    if MISSILE and B[2][0xAF00 - 0x8000] == 5:
        B[2][0xE20F - 0xE000 + 0xAF00 - 0x8000] = 1; played += 1
        m.tr.keyboard = [0, 1 if played < 20 else 0, 0, 0, 0, 0, 0, 1]
    saved = None
    if EDGE and (ticks + 1) % every == 0:
        sim.trace(m.pc, DS, 0, end, 1, None, None, None, None, None); m.pc = regs[24]
        if m.pc != DS: break
        n0 = 0
        while n0 < 32 and B[2][SA + 4 * n0] != 0xD0: n0 += 1
        free = [i for i in range(n0) if B[2][SA + 4 * i] + 1 >= 177 or not B[2][SA + 4 * i + 3] & 15]
        free += list(range(n0, 32))             # slots not shown: hidden, or past the end
        if len(free) >= 5:
            saved = bytes(B[2][SA: SA + 128])
            pats = [B[2][SA + 4 * i + 2] for i in range(n0) if i not in free] or [0]
            k = ticks // every
            ent = [(16 + 8 * (k % 9), 17 + k % 16, 0x8F),          # early clock: x -15 to 0
                   (40 + 8 * (k % 9), 241 + k % 15, 0x0E),         # x 241 to 255
                   (100 - 8 * (k % 9), 225 + k % 16, 0x0D),        # x 225 to 240
                   (130, 255 - k % 15, 0x8B),                      # early clock: x 223 down to 209
                   (20 + 8 * (k % 9), 1 + k % 16, 0x8C)]           # early clock: x -31 to -16, not shown
            last = max(free[:5])
            for slot, (y, x, c) in zip(free, ent):
                B[2][SA + 4 * slot: SA + 4 * slot + 4] = bytes([y, x, pats[(k + slot) % len(pats)], c])
            for i in range(n0, last + 1):       # past the old end: the gap is shown nothing
                if i not in free[:5]: B[2][SA + 4 * i: SA + 4 * i + 4] = bytes([0xC0, 0, 0, 0])
            if last + 1 < 32: B[2][SA + 4 * (last + 1)] = 0xD0
    sim.trace(m.pc, P, 0, end, 1, None, None, None, None, None); m.pc = regs[24]
    if m.pc != P: break
    ticks += 1
    if ticks % every == 0:
        hi = fx(syms['r_scr_hi']); scr = B[5] if hi == 0x40 else B[7]
        pix = bytearray(6144); att = bytearray(768)
        for c in range(768):
            t, l = c >> 8, c & 255; tid = fx(ns + c)
            for r in range(8): pix[(t * 8 + r) * 256 + l] = B[7][((0xDB + 9 * t + r) << 8) - 0xC000 + tid]
            att[c] = B[7][((0xDB + 9 * t + 8) << 8) - 0xC000 + tid]
        sa = 0xEC80 + 0xAF00 - 0xE000 - 0x8000
        n = 0
        while n < 32 and B[2][sa + 4 * n] != 0xD0: n += 1
        if not B[5][syms['spr_on'] - 0x4000]: n = 0     # Konami hid them all (0xD0 at VRAM 3B00)
        for i in reversed(range(n)):
            y, x, p, col = B[2][sa + 4 * i: sa + 4 * i + 4]
            y += 1
            if y >= 177 or not col & 15: continue
            pp = p & 0xFC
            if pp < 24 and pp & 4: nskip += 1; continue     # the ship's second colour: not drawn (ship.asm, 0.100)
            if col & 0x80:
                x -= 32
                if x < -15: continue    # wholly off the left edge
            nspr += 1
            if x < 0 or x > 240: nedge += 1
            pm = syms['spr_pmap'] - 0xC000 + ((p & 0xFC) >> 1)      # this pattern's own ink (spr_pmap)
            ink = B[7][pm + 1] if B[7][pm] in (col & 15, 0x10) else spr_ink[col & 15]
            keep = B[7][pm] == 0x20     # the missile: terrain keeps its colours (attrs_keep)
            if keep and fx(ns + (y >> 3) * 32 + (max(x, 0) >> 3) + 64): nkeep += 1   # over terrain
            if pp < 24: src, base = B[2], syms['ship_pat'] - 0x8000 + pp * 4   # the ship: its own patterns (ship.asm)
            else: src, base = B[7], 0xF800 - 0xC000 + pp * 8
            used = 0; rmin = rmax = None       # (1.1.2) the cells the pixels reach, as sp_trim
            for r in range(16):
                row = src[base + r] << 8 | src[base + 16 + r]
                if row:
                    if rmin is None: rmin = r
                    rmax = r
                    v = (row << 8) >> (x & 7)
                    used |= (4 if v >> 16 else 0) | (2 if v >> 8 & 255 else 0) | (1 if v & 255 else 0)
                yy = y + r
                if yy >= 192: continue
                for k in range(16):
                    if row & (0x8000 >> k):
                        xx = x + k
                        if not 0 <= xx < 256: continue      # clipped at the edges
                        a = ((yy & 0xC0) << 5) | ((yy & 7) << 8) | ((yy & 0x38) << 2) | (xx >> 3)
                        pix[a] |= 0x80 >> (xx & 7)
            if TRIM and not (x < 0 or x > 240):  # the box cut to the pixels (sp_trim); clipped sprites keep theirs
                if rmin is None: continue        # no pixels: not coloured
                cys = range((y + rmin) >> 3, ((y + rmax) >> 3) + 1)
                cols = [i for i in range(3) if used & (4 >> i)]
                ccs = range((x >> 3) + cols[0], (x >> 3) + cols[-1] + 1)
            else:
                cys = range(y >> 3, (y >> 3) + (3 if y & 7 else 2))
                ccs = range(x >> 3, ((x + 15) >> 3) + 1)     # the cells the box covers, on screen
            for cy in cys:
                for cc in ccs:
                    if cy < 24 and 0 <= cc < 32:
                        a0 = att[cy * 32 + cc]
                        if keep:
                            tid = fx(ns + cy * 32 + cc)
                            if tid == 0 or 0xF6 <= tid < 0xF8: att[cy * 32 + cc] = ink & 0x47
                            continue
                        att[cy * 32 + cc] = (a0 & 0x78) | (ink & 7) if a0 & 0x38 else ink   # coloured paper keeps its bright
        if bytes(pix) != bytes(scr[:6144]) or bytes(att) != bytes(scr[6144:6912]):
            bad += 1
            dp = sum(1 for i in range(6144) if pix[i] != scr[i]); da = sum(1 for i in range(768) if att[i] != scr[6144 + i])
            if bad <= 5: print('t=%.2fs %d sprites: %d pixel bytes, %d attributes differ' % ((regs[25] - m.t0) / FR / 50, n, dp, da))
            if bad <= 2 and os.environ.get('SHOW'): print('   ', [(i // 32, i % 32, '%02X' % att[i], '%02X' % scr[6144 + i]) for i in range(768) if att[i] != scr[6144 + i]][:8])
    if saved: B[2][SA: SA + 128] = saved
    sim.trace(m.pc, -1, 0, regs[25] + 4, 1, None, None, None, None, None); m.pc = regs[24]
print('ticks', ticks, 'checked', ticks // every, 'sprites drawn', nspr, 'at the edges', nedge, 'missiles over terrain', nkeep, 'wrong', bad) if MISSILE else print('ticks', ticks, 'checked', ticks // every, 'sprites drawn', nspr, 'at the edges', nedge, 'ship overlays not drawn', nskip, 'wrong', bad)
