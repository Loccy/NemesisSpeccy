"""Compiled sprites, proof of concept in the simulator (10 November 2026).

Runs a 128K snapshot through the first loop (invulnerable, Konami's
all-weapons cheat with NEM_ALL=1, keys_default's fire, no other keys) and
profiles it as pp_cat.py does (PC sampled every 300 T-states, put in a
category by its label).  With a CSPR build (NEM_CSPR=1), each sprite stops
at draw_sprite16.cspr_hook: the code for its pattern (the 32 bytes at DE)
and pixel offset (A) is generated here and put at 2000h, in place of the
ROM (which the game does not use), and the sprite is drawn by it.  Code
sizes are kept per distinct (pattern bytes, offset), by stage, for the
memory such code would need.  Without CSPR the hook is never met: the same
script measures the shipped renderer.

Generated code, entry HL = screen address of the sprite's top line at its
first column: per line, for each non-zero byte of the shifted line,
`ld a,(hl) / or n / ld (hl),a` with `inc l`/`dec l` between columns; then
`inc h / ld a,h / and 7 / call z,FIX` to the next line (FIX at 3F00: the
next character row, as draw_sprite16's own step); `ret` after the last
non-empty line.
usage: pp_cspr.py SNA SYM SECONDS OUT.pkl"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, re, bisect, collections, pickle
sys.path.insert(0, os.environ.get('NEM_SPEC', (_NEM + '/spec')))
sys.path.insert(0, (_NEM + '/reloc'))
from emu import Spectrum, _syms, keys_default
SNA, SYM, SECS, OUT = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
s = Spectrum(SNA); syms = _syms(SYM)
s.mem.banks[0][syms['m1_75F0'] - 0xC000] = 0xC9
sim = s.sim; R = s.regs; tr = s.tr; FR = 70908; SL = 300
HOOK = syms.get('draw_sprite16.cspr_hook', -1)
WIN, FIX = 0x2000, 0x3F00
for rom in s.mem.roms:
    rom[FIX:FIX + 8] = bytes([0x7D, 0xC6, 0x20, 0x6F, 0xD8, 0x7C, 0xD6, 0x08])
    rom[FIX + 8] = 0x67; rom[FIX + 9] = 0xC9
    rom[WIN] = 0xC9                          # until the first sprite (emu.hook's run to pm_tick may draw one)
    rom[0x3E00:0x3E41] = bytes(0x41)
    for it in os.environ.get('CSPR_SET', 'all').split(','):
        if it == 'all': rom[0x3E00:0x3E41] = bytes([1] * 0x41)
        elif it == 'ship': rom[0x3E40] = 1
        elif it.isdigit(): rom[0x3E00 + int(it) // 4] = 1

def gen(pat, sh):
    L, Rb = pat[:16], pat[16:32]
    code = bytearray(); col = 0
    rows = []
    for r in range(16):
        if sh == 0: bs = [L[r], Rb[r]]
        else:
            v = (L[r] << 16 | Rb[r] << 8) >> sh
            bs = [v >> 16 & 255, v >> 8 & 255, v & 255]
        rows.append(bs)
    last = max([r for r in range(16) if any(rows[r])], default=-1)
    for r in range(last + 1):
        for k, b in enumerate(rows[r]):
            if not b: continue
            while col < k: code.append(0x2C); col += 1
            while col > k: code.append(0x2D); col -= 1
            code += bytes([0x7E, 0xF6, b, 0x77])
        if r < last:
            code += bytes([0x24, 0x7C, 0xE6, 0x07, 0xCC, FIX & 255, FIX >> 8])
    code.append(0xC9)
    return bytes(code)

def rd(a, n):
    if a >= 0xC000: b, o = s.mem.banks[tr.out7ffd & 7], a - 0xC000
    elif a >= 0x8000: b, o = s.mem.banks[2], a - 0x8000
    else: b, o = s.mem.banks[5], a - 0x4000
    return bytes(b[o:o + n])

# categories, as pp_cat.py (scrollbench.py's rules)
os.environ['NEM_TARGET'] = 'spec'
import gen as G
g = G.Gen(open((_NEM + '/nem.rom'), 'rb').read())
fixed = sorted((v, k) for k, v in syms.items() if v < 0xC000 and '.' not in k); fk = [v for v, k in fixed]
PN = {'A': 0, 'B': 3, 'C': 4, 'D': 6, 'E': 1}
paged = collections.defaultdict(list)
for k, v in syms.items():
    if v < 0xC000 or '.' in k: continue
    mm = re.match(r'(?:([A-Z])_)?m(\d+)_([0-9A-F]{4})$', k)
    if mm:
        sec = mm.group(1) or g.home.get((int(mm.group(2)), int(mm.group(3), 16)))
        if sec in PN: paged[PN[sec]].append((v, k))
    else:
        for p in (0, 1, 3, 4, 6, 7): paged[p].append((v, k))
for p in paged: paged[p].sort()
pkeys = {p: [v for v, k in L] for p, L in paged.items()}
RULES = [('sound', r'^(?:[A-Z]_)?m[78]_'), ('konami', r'^(?:[A-Z]_)?m\d+_'),
 ('cells', r'^(draw_cells|render_frame|bar_style|render_init|rf_|pm_tiles|pm_render|vw_)'),
 ('sprites', r'^(draw_sprite|draw_sprites|erase_sprites|spr_|edge|attrs_keep|ship_)'),
 ('stars', r'^(redraw_star|draw_stars|star_|blink_native)'),
 ('track', r'^(nm_|upl_|chg_|plat_upload_map|full_?cmp|dirty)'),
 ('paging', r'^(out_page|far_|nfar_|map_|set_page|unborrow|borrow)'),
 ('wait', r'^(pm_wait|pace_|wait_shown|plat_main)')]
cache = {}
def cat(pc, page):
    if pc < 0x4000: return 'sprites'          # the compiled code
    key = (pc, page if pc >= 0xC000 else -1)
    if key in cache: return cache[key]
    if pc < 0xC000:
        i = bisect.bisect_right(fk, pc) - 1; n = fixed[i][1] if i >= 0 else '?'
    else:
        Lp = paged.get(page, []); i = bisect.bisect_right(pkeys.get(page, []), pc) - 1
        n = Lp[i][1] if i >= 0 else 'page%d' % page
    c = 'other'
    for cc, r in RULES:
        if re.match(r, n): c = cc; break
    if pc >= 0xC000 and page == 6 and 0xE400 <= pc < 0xE800: c = 'track'
    cache[key] = c; return c

CHECK = [0]; BAD = [0]
sizes = {}                                   # (pattern bytes, offset) -> code size
used = collections.defaultdict(collections.Counter)    # stage -> (pattern, offset) -> draws
FRAMES = []; flips = 0; disp = tr.out7ffd & 8
ticks = 0; last3 = s.k(0xE003); stage_start = {}; seen8 = False
for f in range(int(SECS * 50)):
    in_play = s.k(0xE000) == 5
    s.hook(advance=True); tr.keyboard = keys_default(f)
    end = s.t0 + (f + 1) * FR; C = collections.Counter(); t0 = ticks
    while R[25] < end:
        t = R[25]
        sim.trace(s.pc, HOOK, 0, min(end, R[25] + SL), 1, None, None, None, None, None); s.pc = R[24]
        C[cat(s.pc, tr.out7ffd & 7)] += R[25] - t
        if s.pc == HOOK:
            de = R[4] << 8 | R[5]; sh = R[0] & 7
            pat = rd(de, 32); key = (pat, sh)
            code = sizes.get(key)
            if code is None:
                code = gen(pat, sh); sizes[key] = code
            for rom in s.mem.roms: rom[WIN:WIN + len(code)] = code
            used[s.k(0xE061)][key] += 1
            hl = R[6] << 8 | R[7]
            if CHECK[0] < 3000 and hl >= 0x4000:
                bank = s.mem.banks[5] if hl < 0x8000 else s.mem.banks[tr.out7ffd & 7]
                base = 0x4000 if hl < 0x8000 else 0xC000
                before = bytes(bank[0:6144]); ret = s.pc + 3
            t = R[25]
            sim.trace(s.pc, -1, 1, end, 1, None, None, None, None, None); s.pc = R[24]   # the call itself
            C['sprites'] += R[25] - t
            if CHECK[0] < 3000 and hl >= 0x4000:
                t = R[25]; sim.trace(s.pc, ret, 0, end + FR, 1, None, None, None, None, None); s.pc = R[24]; C['sprites'] += R[25] - t
                exp = bytearray(before)
                y0 = ((hl >> 8) & 7) | ((hl >> 2) & 0x38) | ((hl >> 5) & 0xC0); y0 = (((hl - base) >> 5) & 0xC0) | (((hl - base) >> 2) & 0x38) | (((hl - base) >> 8) & 7)
                cx = hl & 31
                for r in range(16):
                    y = y0 + r
                    if y > 191: break
                    if sh == 0: bs = [pat[r], pat[16 + r]]
                    else:
                        v = (pat[r] << 16 | pat[16 + r] << 8) >> sh; bs = [v >> 16 & 255, v >> 8 & 255, v & 255]
                    for k2, bb in enumerate(bs):
                        a2 = ((y & 0xC0) << 5) | ((y & 7) << 8) | ((y & 0x38) << 2) | (cx + k2)
                        exp[a2] |= bb
                now = bytes(bank[0:6144])
                if now != bytes(exp): BAD[0] += 1
                CHECK[0] += 1
    s.frame = f + 1
    e = s.k(0xE003); ticks += (e - last3) & 255; last3 = e
    d = tr.out7ffd & 8; drew = int(d != disp); disp = d
    stg = s.k(0xE061)
    FRAMES.append((f, int(in_play), stg, ticks - t0, drew, dict(C)))
    if in_play:
        if stg == 8: seen8 = True
        key = (2 if seen8 and stg != 8 else 1, stg)
        if key not in stage_start: stage_start[key] = (f, ticks); print('stage', key, f, flush=True)
        if key[0] == 2: break
sz = {k: len(v) for k, v in sizes.items()}
pickle.dump(dict(FRAMES=FRAMES, stage_start=stage_start, sizes=sz,
                 used={k: dict(v) for k, v in used.items()}), open(OUT, 'wb'))
print('checked', CHECK[0], 'bad', BAD[0]); print('done', f, 'distinct (pattern, offset):', len(sz), 'bytes', sum(sz.values()))
