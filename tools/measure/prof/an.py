import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, os, pickle, re, bisect, collections
sys.path.insert(0, (_NEM + '/spec')); sys.path.insert(0, (_NEM + '/reloc'))
os.environ['NEM_TARGET'] = 'spec'
from skoolkit.snapshot import Snapshot
D = pickle.load(open(sys.argv[1], 'rb')); TOP = int(sys.argv[2]) if len(sys.argv) > 2 else 70
acc, cnt, events, meta = D['acc'], D['cnt'], D['events'], D['meta']
syms = {}
for l in open(D['sym']):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
from emu import Spectrum
_s = Spectrum(D['sna']); banks = _s.mem.banks
def rd(pc, page):
    if pc < 0x4000: return 0
    if pc < 0x8000: return banks[5][pc-0x4000]
    if pc < 0xC000: return banks[2][pc-0x8000]
    return banks[page][pc-0xC000]
import gen as G
g = G.Gen(open((_NEM + '/nem.rom'), 'rb').read())
PN = {'A': 0, 'B': 3, 'C': 4, 'D': 6, 'E': 1}
# function starts: platform non-local labels; call targets among executed instructions; far stub targets
fstart = collections.defaultdict(dict)       # page (-1 fixed) -> addr -> name
klabel = {}                                  # (page, addr) -> konami label
for k, v in syms.items():
    if '.' in k: continue
    mm = re.match(r'(?:([A-Z])_)?m(\d+)_([0-9A-F]{4})$', k)
    if mm:
        sec = mm.group(1) or g.home.get((int(mm.group(2)), int(mm.group(3), 16)))
        pg = PN.get(sec, -1) if v >= 0xC000 else -1
        klabel[(pg, v)] = k
    else:
        if v >= 0xC000:
            for p in (0, 1, 3, 4, 6, 7): fstart[p].setdefault(v, k)
        else: fstart[-1][v] = k
CALLS = {0xCD, 0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC}
for key in cnt:
    pc = key & 0xFFFF; page = key >> 16 if pc >= 0xC000 else -1
    op = rd(pc, key >> 16)
    if op in CALLS:
        t = rd(pc+1, key >> 16) | rd(pc+2, key >> 16) << 8
        tp = (key >> 16) if t >= 0xC000 else -1
        if t >= 0xC000 and pc < 0xC000: continue          # from fixed into a page: page unknown here (stubs handle)
        nm = klabel.get((tp, t))
        if nm: fstart[tp].setdefault(t, nm)
for k, v in syms.items():
    mm = re.match(r'n?far_((?:[A-Z]_)?m(\d+)_([0-9A-F]{4}))', k)
    if mm and mm.group(1) in syms:
        t = syms[mm.group(1)]
        sec = g.home.get((int(mm.group(2)), int(mm.group(3), 16)))
        pg = PN.get(sec, -1) if t >= 0xC000 else -1
        fstart[pg].setdefault(t, mm.group(1))
# every konami label that is a jump-table target is missed: accept
fk = {p: sorted(d) for p, d in fstart.items()}
def func(key):
    pc = key & 0xFFFF; page = key >> 16 if pc >= 0xC000 else -1
    L = fk.get(page, []); i = bisect.bisect_right(L, pc) - 1
    if i < 0: return 'page%d?%04X' % (page, pc)
    a = L[i]; n = fstart[page][a]
    if pc >= 0xC000 and page == 6 and 0xE400 <= pc < 0xE800: n = 'full_cmp'
    return n
RULES = [('sound', r'^(?:[A-Z]_)?m[78]_'), ('konami', r'^(?:[A-Z]_)?m\d+_'),
 ('cells', r'^(draw_cells|render_frame|bar_style|rf_|dirty_all)'),
 ('sprites', r'^(draw_sprite|draw_sprites|erase_sprites|spr_|edge|attrs_keep|ship_|sp_)'),
 ('stars', r'^(redraw_star|draw_stars|star_|blink_native|bl_)'),
 ('tiles', r'^(tick_tiles|note_|invalidate_tile|redraw_tile|ensure)'),
 ('track', r'^(nm_|upl_|chg_|plat_upload_map|full_?cmp|dirty_cell)'),
 ('paging', r'^(out_page|far_|nfar_|map_|set_page|unborrow|borrow)'),
 ('standins', r'^(bios_|vram_|vdp|vw_|dcompr|read_joy|snd_)'),
 ('input', r'^(kb_|read_keyboard|kempston|fire_hold|hold)'),
 ('interrupt', r'^(isr|run_sound)'),
 ('pacing', r'^(pm_|pace_|wait_shown|request_flip|plat_main|far_pace)'),
 ('loads', r'^(nl_|nlb_|dz_)')]
def cat(n):
    for c, r in RULES:
        if re.match(r, n): return c
    return 'other'
ft = collections.Counter(); fc = collections.Counter()
for key, t in acc.items(): ft[func(key)] += t
# calls: executions of the function's first instruction
for p, d in fstart.items():
    for a, n in d.items():
        if p == -1: fc[n] += cnt.get(a, 0)
        else: fc[n] += cnt.get(a | p << 16, 0)
ev = collections.Counter(e for e, t in events)
ticks = ev['pm_tick']; renders = ev['pm_render']; frames = ev['frame']
tot = sum(acc.values())
print('frames %d, ticks %d (%.2f/s), pictures %d (%.2f/s), drawn %.0f%%, T/tick %d' % (frames, ticks, ticks*50/frames, renders, renders*50/frames, 100*renders/ticks, tot/ticks))
ct = collections.Counter()
for n, t in ft.items(): ct[cat(n)] += t
print('\nby category, T per tick:')
for c, t in ct.most_common(): print('  %-10s %8d  %5.1f%%' % (c, t/ticks, 100*t/tot))
print('\ntop functions (exclusive T per tick, calls per tick, T per call):')
for n, t in ft.most_common(TOP):
    c = fc.get(n, 0)
    print('  %-9s %-22s %7d %5.1f%%  %7.2f calls  %s' % (cat(n), n, t/ticks, 100*t/tot, c/ticks, ('%6d T/call' % (t/c)) if c else ''))
pickle.dump(dict(ft=ft, fc=fc, ticks=ticks, renders=renders, frames=frames), open(sys.argv[1] + '.an', 'wb'))
