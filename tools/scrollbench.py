"""Scroll ticks against the others (0.108): bench.py's deterministic workload (test build, every tick drawn), with each
tick's T-states split by category, then the current pacing modelled with
categories scaled.  usage: catbench.py TICKS SKIP"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, re, math, bisect, collections, statistics, json
NEM_ROOT = os.environ.get('XROOT', _NEM)
sys.path.insert(0, NEM_ROOT + '/spec'); sys.path.insert(0, NEM_ROOT + '/reloc')
from emu import Spectrum
HERE = NEM_ROOT + '/spec'
syms = {}
for l in open(HERE + '/nemesis_test.sym'):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
os.environ['NEM_TARGET'] = 'spec'
import gen as G
g = G.Gen(open(NEM_ROOT + '/nem.rom', 'rb').read())
fixed = sorted((v, k) for k, v in syms.items() if v < 0xC000 and '.' not in k)
fk = [v for v, k in fixed]
PN = {'A': 0, 'B': 3, 'C': 4, 'D': 6, 'E': 1}
paged = collections.defaultdict(list)
for k, v in syms.items():
    if v < 0xC000 or '.' in k: continue
    mm = re.match(r'(?:([A-Z])_)?m(\d+)_([0-9A-F]{4})$', k)
    if mm:
        sec = mm.group(1) or g.home.get((int(mm.group(2)), int(mm.group(3), 16)))
        if sec in PN: paged[PN[sec]].append((v, k))
    else:
        for p in (0, 1, 3, 4, 6, 7): paged[p].append((v, k))   # platform labels: page unknown, add everywhere
for p in paged: paged[p].sort()
pkeys = {p: [v for v, k in L] for p, L in paged.items()}
RULES = [('sound', r'^(?:[A-Z]_)?m[78]_'), ('konami', r'^(?:[A-Z]_)?m\d+_'),
 ('cells', r'^(draw_cells|render_frame|bar_style)'),
 ('sprites', r'^(draw_sprite|draw_sprites|erase_sprites|spr_|edge|attrs_keep|ship_)'),
 ('stars', r'^(redraw_star|draw_stars|star_|blink_native)'),
 ('convert', r'^(conv|cv_|ensure_tile|recolour|tile_post|nearer|cache|rule|stage_|dz_|logo|tick_tiles|tt_|flag_tile|note_tile|invalidate_tile|load_tile)'),
 ('track', r'^(nm_|upl_|chg_|plat_upload_map|full_?cmp|dirty)'),
 ('paging', r'^(out_page|far_|nfar_|map_|set_page|unborrow|borrow)'),
 ('standins', r'^(bios_|vram_|vbulk|descomprime|dcompr|dc_|vdp|wrtpsg|psg)'),
]
cache = {}
LAB = collections.Counter()
FC = sorted((v, k) for k, v in syms.items() if k.startswith('full_cmp') or k == 'full_cmp')
def lab(pc, page):
    if pc >= 0xC000 and page == 6 and 0xE400 <= pc < 0xE800:
        i = bisect.bisect_right([v for v, k in FC], pc) - 1; return FC[i][1] if i >= 0 else 'full_cmp?'
    if pc < 0xC000:
        i = bisect.bisect_right(fk, pc) - 1; return fixed[i][1] if i >= 0 else '?'
    L = paged.get(page, []); i = bisect.bisect_right(pkeys.get(page, []), pc) - 1
    return L[i][1] if i >= 0 else 'page%d' % page
def cat(pc, page):
    key = (pc, page if pc >= 0xC000 else -1)
    if key in cache: return cache[key]
    if pc < 0xC000:
        i = bisect.bisect_right(fk, pc) - 1; n = fixed[i][1] if i >= 0 else '?'
    else:
        L = paged.get(page, []); i = bisect.bisect_right(pkeys.get(page, []), pc) - 1
        n = L[i][1] if i >= 0 else 'page%d' % page
    c = 'other'
    for cc, r in RULES:
        if re.match(r, n): c = cc; break
    if c == 'other' and n.startswith('page3'): c = 'convert'
    if pc >= 0xC000 and page == 6 and 0xE400 <= pc < 0xE800: c = 'track'   # fullcmp_gen (page D), not page C's rules at the same addresses
    cache[key] = c; return c
N = int(sys.argv[1]); SKIP = int(sys.argv[2]); SL = 300; FR = 70908
spec = Spectrum(HERE + '/nemesis_test.sna')
spec.mem.banks[0][syms['m1_75F0'] - 0xC000] = 0xC9
sim = spec.sim; R = spec.regs; tr = spec.tr
LOOP = syms['plat_main.loop']; W = syms['pm_wait']; P = syms['pm_render']; F = syms['pm_flip']
def run(a):
    sim.trace(spec.pc, a, 0, R[25] + FR * 1000, 1, None, None, None, None, None); spec.pc = R[24]
def runs(a, C):
    while True:
        t = R[25]
        sim.trace(spec.pc, a, 0, R[25] + SL, 1, None, None, None, None, None); spec.pc = R[24]
        c = cat(spec.pc, tr.out7ffd & 7); C[c] += R[25] - t
        if RECORD[0]: TL[(c, lab(spec.pc, tr.out7ffd & 7))] += R[25] - t
        if spec.pc == a: return
def keys_for_tick(t, started):
    if not started: return (t % 40) < 4
    return t % 8 < 4
run(LOOP); rows = []; RECORD = [False]; TL = collections.Counter(); LS = collections.Counter(); LO = collections.Counter(); NS = [0, 0]
for i in range(N):
    kb = [0] * 8
    if keys_for_tick(i, spec.k(0xE000) == 5): kb[7] |= 1
    tr.keyboard = kb; d0 = spec.k(0xE063); RECORD[0] = i >= SKIP; TL.clear()
    CL = collections.Counter(); CD = collections.Counter()
    if 'pm_eager' in syms:
        runs(syms['pm_eager'], CL); t = R[25]; run(syms['pm_eager_end']); CL['eager'] += R[25] - t
    if spec.pc != W: runs(W, CL)
    run(P); runs(F, CD)
    sim.trace(spec.pc, -1, 1, R[25] + FR, 1, None, None, None, None, None); spec.pc = R[24]
    run(LOOP)
    if i >= SKIP and spec.k(0xE000) == 5:
        sc = spec.k(0xE063) != d0
        rows.append((dict(CL), dict(CD), sc))
        (LS if sc else LO).update(TL); NS[0 if sc else 1] += 1
json.dump(rows, open(sys.argv[3], 'w'))
ns, no = NS
print('scroll ticks %d, others %d' % (ns, no))
keys = set(LS) | set(LO)
ex = sorted((((LO[k] / no) if os.environ.get('SORT') == 'other' else (LS[k] / ns - LO[k] / no), k) for k in keys), reverse=True)
print('%8s %8s %8s  %s' % ('scroll', 'other', 'excess', 'routine'))
for e, k in ex[:int(os.environ.get('TOP', '40'))]:
    print('%8d %8d %8d  %-9s %s' % (LS[k] / ns, LO[k] / no, e, k[0], k[1]))
print('total %8d %8d %8d' % (sum(LS.values()) / ns, sum(LO.values()) / no, sum(LS.values()) / ns - sum(LO.values()) / no))
