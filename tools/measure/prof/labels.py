"""Function-level labels for (pc, page) in a 128K build: platform labels, and Konami's code grouped by call targets."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, os, re, bisect, collections
sys.path.insert(0, (_NEM + '/spec')); sys.path.insert(0, (_NEM + '/reloc'))
os.environ['NEM_TARGET'] = 'spec'
PN = {'A': 0, 'B': 3, 'C': 4, 'D': 6, 'E': 1}
RULES = [('sound', r'^(?:[A-Z]_)?m[78]_'), ('konami', r'^(?:[A-Z]_)?m\d+_'),
 ('cells', r'^(draw_cells|render_frame|bar_style|rf_|dirty_all)'),
 ('sprites', r'^(draw_sprite|draw_sprites|erase_sprites|spr_|edge|attrs_keep|ship_|sp_)'),
 ('stars', r'^(redraw_star|draw_stars|star_|blink_native|bl_)'),
 ('tiles', r'^(tick_tiles|note_|invalidate_tile|redraw_tile|ensure)'),
 ('track', r'^(nm_|upl_|chg_|plat_upload_map|full_?cmp|full_grp|dirty_cell)'),
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
class Labels:
    def __init__(self, sna, sym):
        from emu import Spectrum
        import gen as G
        self.syms = syms = {}
        for l in open(sym):
            m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
            if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
        banks = Spectrum(sna).mem.banks
        def rd(pc, page):
            if pc < 0x4000: return 0
            if pc < 0x8000: return banks[5][pc-0x4000]
            if pc < 0xC000: return banks[2][pc-0x8000]
            return banks[page][pc-0xC000]
        self.rd = rd
        g = G.Gen(open((_NEM + '/nem.rom'), 'rb').read())
        fstart = collections.defaultdict(dict); klabel = {}
        for k, v in syms.items():
            if '.' in k: continue
            mm = re.match(r'(?:([A-Z])_)?m(\d+)_([0-9A-F]{4})$', k)
            if mm:
                sec = mm.group(1) or g.home.get((int(mm.group(2)), int(mm.group(3), 16)))
                pg = PN.get(sec, -1) if v >= 0xC000 else -1
                klabel[(pg, v)] = k
            elif re.match(r'(data_|section_|native_end|low_end|page_|platform_|ctl_text)', k): continue
            else:
                if v >= 0xC000:
                    for p in (0, 1, 3, 4, 6, 7): fstart[p].setdefault(v, k)
                else: fstart[-1][v] = k
        CALLS = {0xCD, 0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC}
        for (pg, pc), nm in klabel.items():
            page = pg if pg >= 0 else 0
            if rd(pc, page) in CALLS:
                t = rd(pc+1, page) | rd(pc+2, page) << 8
                tp = pg if t >= 0xC000 else -1
                if t >= 0xC000 and pc < 0xC000: continue
                n2 = klabel.get((tp, t))
                if n2: fstart[tp].setdefault(t, n2)
        for k, v in syms.items():
            mm = re.match(r'n?far_((?:[A-Z]_)?m(\d+)_([0-9A-F]{4}))$', k)
            if mm and mm.group(1) in syms:
                t = syms[mm.group(1)]
                sec = g.home.get((int(mm.group(2)), int(mm.group(3), 16)))
                pg = PN.get(sec, -1) if t >= 0xC000 else -1
                fstart[pg].setdefault(t, mm.group(1))
        for b, lo, hi in getattr(G, 'HOT_CLONES', []):          # copies in uncontended memory (1.2): each a function
            k = 'H_m%d_%04X' % (b, lo)
            if k in syms: fstart[-1][syms[k]] = k
        if 'section_hot_end' in syms: fstart[-1].setdefault(syms['section_hot_end'], 'pace_data')
        self.fstart = fstart; self.fk = {p: sorted(d) for p, d in fstart.items()}; self.cache = {}
    def func(self, key):
        c = self.cache.get(key)
        if c is not None: return c
        pc = key & 0xFFFF; page = key >> 16 if pc >= 0xC000 else -1
        L = self.fk.get(page, []); i = bisect.bisect_right(L, pc) - 1
        if i < 0: n = 'page%d?' % page
        else: n = self.fstart[page][L[i]]
        if pc >= 0xC000 and page == 6 and 0xE400 <= pc < 0xE800 and not n.startswith('nx_'): n = 'full_cmp'
        if pc < 0x4000: n = 'rom?'
        self.cache[key] = n; return n
