"""Check the converted tile set: every tile not waiting for conversion must
match its MSX pattern and colours under its own ink/paper (each pixel goes to
whichever of ink and paper is nearer, as nearer_ink decides).

usage: check_tiles.py SECONDS [skip_seconds] [every_n_ticks]
"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re, os
sys.path.insert(0, NEM_ROOT + '/spec')
from emu import Spectrum, keys_default
from stage_rules import rule, invert
HERE = NEM_ROOT + '/spec'
syms = {}
for l in open(os.path.join(HERE, 'nemesis.sym')):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
secs = float(sys.argv[1]); skip = float(sys.argv[2]) if len(sys.argv) > 2 else 0
every = int(sys.argv[3]) if len(sys.argv) > 3 else 10
m = Spectrum()
for f in range(int(skip * 50)): m.run_frame()
sim = m.sim; regs = m.regs; FR = 70908; B = m.mem.banks
def fixed(a): return B[2][a - 0x8000] if a >= 0x8000 else B[5][a - 0x4000]
cvd = syms['cv_dist']
def D(br, mc, z):
    a = cvd + br * 256 + mc * 16 + z * 2
    return fixed(a) | fixed(a + 1) << 8
def plain_ok(p, pats, cols, gots):
    ink, pap, br = p & 7, p >> 3 & 7, p >> 6 & 1
    for r in range(8):
        exp = 0
        for k in range(8):
            mc = cols[r] >> 4 if pats[r] & (128 >> k) else cols[r] & 15
            if ink != pap and D(br, mc, ink) < D(br, mc, pap): exp |= 128 >> k
        if gots[r] != exp: return False
    return True
end = regs[25] + int(secs * 50 * FR); P = syms['rf_cells']
ticks = bad = 0; bystage = {}
while regs[25] < end:
    m.tr.keyboard = keys_default(regs[25] // FR)
    m.hook()                    # NEM_ALL=1: all weapons once play starts (emu.py)
    sim.trace(m.pc, P, 0, end, 1, None, None, None, None, None); m.pc = regs[24]
    if m.pc != P: break
    ticks += 1
    if ticks % every == 0:
        wrong = []
        dz_seen = fixed(syms['dz_on'])     # the dissolve's tiles stay as it left them until the next load
        for t in range(3):
            for i in range(256):
                o = t * 32 + (i >> 3); bit = 1 << (i & 7)
                if (fixed(syms['tile_cdirty'] + o) | fixed(syms['tile_pdirty'] + o)) & bit: continue
                attr = B[7][((0xDB + 9 * t + 8) << 8) - 0xC000 + i]
                if attr & 0x80: continue                # flagged: waiting for conversion when next drawn
                if t == 2 and (0x15 <= i <= 0x42 or i == 0x0C) and attr in (0x4F, 0x46): continue   # the power-up bar's own design (barstyle.asm; 0C a taken item's box)
                if 0x77 <= i <= 0x7A: continue          # the nuke capsule, coloured cyan (tile_post)
                ink, pap, br = attr & 7, attr >> 3 & 7, attr >> 6 & 1
                if t < 2 and i >= 0x8D and 2 <= fixed(0xAF00) < 5:
                    continue        # between the title and the stage: may still hold the logo's look, not on screen
                if fixed(0xAF00) < 2 and t < 2 and i >= 0x8D:   # the title's logo (logo_tile)
                    pats = [B[6][0xE800 - 0xC000 + t * 0x800 + i * 8 + r] for r in range(8)]
                    fgs = [B[4][0xE800 - 0xC000 + t * 0x800 + i * 8 + r] >> 4 for r in range(8)]
                    cyan = any(p and f in (5, 7) for p, f in zip(pats, fgs))
                    want = [(0x45 if cyan else 0x47)]
                    for r in range(8):
                        st = fgs[r] == 5 or (fgs[r] == 4 and cyan)
                        exp = pats[r] & ((0xAA if (8 - r) & 1 else 0x55) if st else 0xFF)
                        got = B[7][((0xDB + 9 * t + r) << 8) - 0xC000 + i]
                        if got != exp: wrong.append((t, '%02X' % i, r, '%02X' % got, '%02X' % exp)); break
                    if attr != want[0]: wrong.append((t, '%02X' % i, 'attr', '%02X' % attr, '%02X' % want[0]))
                    continue
                pats = [B[6][0xE800 - 0xC000 + t * 0x800 + i * 8 + r] for r in range(8)]
                cols = [B[4][0xE800 - 0xC000 + t * 0x800 + i * 8 + r] for r in range(8)]
                gots = [B[7][((0xDB + 9 * t + r) << 8) - 0xC000 + i] for r in range(8)]
                dist = fixed(0xAF63) | fixed(0xAF64) << 8
                if dz_seen and all(c & 0x0E == 0 for c in cols) and plain_ok(attr, pats, cols, gots):
                    continue    # Konami's dissolve: no rules for a tile on black (dz_tile, 0.107)
                ru = rule(fixed(0xAF61), t, i, pats, cols, dist) if fixed(0xAF00) >= 2 or t == 2 or i < 0x8D else None
                if fixed(0xAF61) == 3 and dist >= 0x195 and not ru:     # past the Moai section: a tile converted
                    ru = rule(3, t, i, pats, cols, 0)                    # before it may still show the rule
                    if ru:
                        ru = ('either', ru[1])                           # as the fit left it, or recoloured
                if ru and ru[0] == 'paint':         # the stage colour rules (rules.asm)
                    er, ea = invert(ru[1], ru[2])
                    if er != gots or ea != attr:
                        wrong.append((t, '%02X' % i, 'rule', '%02X' % attr, '%02X' % ea, bytes(gots).hex(), bytes(er).hex()))
                    continue
                cands = [attr]
                if ru and ru[0] == 'either':
                    cands = [attr] + [p for p in range(128) if ru[1](p) == attr]
                elif ru:                            # recoloured: some attribute the fit chose maps to this one
                    cands = [p for p in range(128) if ru[1](p) == attr]
                ok = False
                for p in cands:
                    ink, pap, br = p & 7, p >> 3 & 7, p >> 6 & 1
                    miss = None
                    for r in range(8):
                        pat, col = pats[r], cols[r]
                        exp = 0
                        for k in range(8):
                            mc = col >> 4 if pat & (128 >> k) else col & 15
                            if ink != pap and D(br, mc, ink) < D(br, mc, pap): exp |= 128 >> k
                        if gots[r] != exp: miss = (t, '%02X' % i, r, '%02X' % gots[r], '%02X' % exp); break
                    if miss is None: ok = True; break
                if not ok: wrong.append(miss if cands else (t, '%02X' % i, 'no preimage', '%02X' % attr))
        if wrong:
            bad += 1
            bystage[fixed(0xAF61)] = bystage.get(fixed(0xAF61), 0) + 1
            if bystage[fixed(0xAF61)] <= 3: print('stage %d state %d t=%.2fs %d tiles, e.g. %s' % (fixed(0xAF61), fixed(0xAF00), (regs[25] - m.t0) / FR / 50, len(wrong), wrong[:4]))
    sim.trace(m.pc, -1, 0, regs[25] + 4, 1, None, None, None, None, None); m.pc = regs[24]
print('ticks', ticks, 'checked', ticks // every, 'wrong', bad, 'by stage', bystage)
