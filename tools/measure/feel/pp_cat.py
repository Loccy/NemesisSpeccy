"""Speed and smoothness of one build over the first two stages (0.109).

Scripted play: the ship invulnerable, fire tapped (keys_default's SPACE
rhythm), and every LAG_EVERY frames in play a press of up or down (Q / A,
towards the middle of the screen) held until the screen shows the ship
moved.  Measured:
  * each stage's length (from its first tick in play to the next stage's);
  * game ticks a second (Konami's tick counter, E003) and screens a second
    (flips of the displayed screen, 7FFD bit 3);
  * frames between screens, and game ticks advanced per screen;
  * input lag: frames from the press (keys set at the start of the frame)
    to the frame whose displayed screen first shows the ship moved, plus the
    beam's time from the top of the frame to the ship's line.
Which tick a screen shows is taken at pm_render, when it is drawn: Konami's
tick count and the ship's Y in its sprite list then.

NOPRESS=1: no up/down presses (no lag figures).  LOOP=1: on to the end of
the first loop (with NEM_ALL=1 for Konami's all-weapons cheat, as the
checkers' all-stages runs), per stage: seconds, ticks and screens a second,
motion evenness and ticks per screen, frames between screens (gaps), how
many gaps were 4 frames or more (long_gaps: the spikes), and the fewest
screens in any one second (worst_s).

usage: perfprofile.py SNA SYM SECONDS OUT.json
"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, json, collections, statistics
sys.path.insert(0, os.environ.get('NEM_SPEC', (_NEM + '/spec')))
import emu
from emu import Spectrum, _syms, keys_default

SNA, SYM, SECS, OUT = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]

NEM_ROOT = _NEM
sys.path.insert(0, NEM_ROOT + '/reloc')
import re, bisect
syms = {}
for l in open(SYM):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
os.environ['NEM_TARGET'] = 'spec'
import gen as G
g = G.Gen(open((_NEM + '/nem.rom'), 'rb').read())
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

SL = 300
WAITS = set(k for k in ('pm_wait',) if k in syms)
def cat2(pc, page):
    c = cat(pc, page)
    if c == 'other':
        n = lab(pc, page)
        if n.startswith(('pm_wait', 'pace_', 'wait_shown')) or n in ('plat_main',): c = 'wait/pace'
        elif n.startswith(('nl_', 'nlb_')): c = 'loads'
        elif n.startswith(('kb_', 'read_keyboard', 'kempston', 'fire_hold', 'read_joystick')): c = 'input'
        elif n.startswith(('isr', 'run_sound', 'request_flip', 'pm_flip', 'pm_tick')): c = 'interrupt/flip'
        elif n.startswith(('render_init', 'rf_', 'pm_tiles', 'pm_render', 'vw_')): c = 'cells'
        OTHER[n] += 1
    return c
OTHER = collections.Counter()
FC_T = collections.Counter(); OL = collections.Counter()      # per frame: category -> T-states
FRAMES = []                        # (f, in play, stage, ticks this frame, drew, {cat: T})
def slice_to(stop, end, C):
    while True:
        t = R[25]
        sim.trace(s.pc, stop, 0, min(end, R[25] + SL), 1, None, None, None, None, None); s.pc = R[24]
        c2 = cat2(s.pc, tr.out7ffd & 7); C[c2] += R[25] - t
        if c2 == 'other': OL[lab(s.pc, tr.out7ffd & 7)] += R[25] - t
        if s.pc == stop or R[25] >= end: return
PRESS = os.environ.get('NOPRESS') != '1'
LOOP = os.environ.get('LOOP') == '1'
LAG_EVERY = 97                       # frames between presses (not a multiple of 2, 3 or 5)
FR = 70908
s = Spectrum(SNA); sy = _syms(SYM)
s.mem.banks[0][sy['m1_75F0'] - 0xC000] = 0xC9          # invulnerable
sim = s.sim; R = s.regs; tr = s.tr
PMR = sy['pm_render']
SPR = 0xEC80                                            # Konami's sprite list (MSX address)

def ship_y():
    for i in range(32):
        y = s.k(SPR + 4 * i); p = s.k(SPR + 4 * i + 2)
        if y == 0xD0: break
        if p in (0, 8, 16): return y
    return None

ticks_total = 0; last_e003 = s.k(0xE003)
rendered = {}                                           # screen bank bit -> (tick count, ship y)
flips = []                                              # (frame, tick shown)
stage_start = {}; play_frames = 0; play_ticks = 0; seen8 = False
lag = []; press = None                                  # (frame, y0, key)
next_press = 0
disp = tr.out7ffd & 8
TL = []; shown = (None, None)
for f in range(int(SECS * 50)):
    in_play = s.k(0xE000) == 5
    kb = keys_default(f)
    if PRESS and in_play and press is None and f >= next_press:
        y0 = ship_y()
        if y0 is not None:
            press = (f, y0, 'A' if y0 < 90 else 'Q')
    if press is not None and f - press[0] > 50:
        press = None; next_press = f + LAG_EVERY       # no movement shown in a second: give up
    if press is not None:
        if press[2] == 'Q': kb[2] |= 1
        else: kb[1] |= 1
    s.hook(advance=True)
    tr.keyboard = kb
    end = s.t0 + (f + 1) * FR
    C = collections.Counter(); t_before = ticks_total; drew = 0
    while True:
        slice_to(PMR, end, C)
        e = s.k(0xE003); ticks_total += (e - last_e003) & 255; last_e003 = e
        if s.pc != PMR or R[25] >= end:
            break
        hidden = (tr.out7ffd & 8) ^ 8
        rendered[hidden] = (ticks_total, ship_y()); drew += 1
        t = R[25]; sim.trace(s.pc, -1, 1, end, 1, None, None, None, None, None); s.pc = R[24]; C['cells'] += R[25] - t
    s.frame = f + 1
    e = s.k(0xE003); ticks_total += (e - last_e003) & 255; last_e003 = e
    FRAMES.append((f, int(in_play), s.k(0xE061), ticks_total - t_before, drew, dict(C)))
    st = s.k(0xE061)
    if in_play:
        play_frames += 1
        if st == 8: seen8 = True
        key = (2 if seen8 and st != 8 else 1, st)       # (loop, stage)
        if key not in stage_start: stage_start[key] = (f, ticks_total)
    d = tr.out7ffd & 8
    if d != disp:
        disp = d
        t, y = rendered.get(d, (None, None))
        flips.append((f, t))
        if press is not None and y is not None and y != press[1]:
            line = 64 + (y + 1) % 256                   # sprite's top line: 64 lines of top border
            lag.append(f - press[0] + line / 312)       # flipped by the interrupt at this frame's start
            press = None; next_press = f + 1 + LAG_EVERY
    if d == disp and len(flips) and flips[-1][0] == f: pass
    shown = rendered.get(disp, (None, None))
    TL.append((f, int(in_play), st, shown[0], shown[1], ticks_total, s.k(0xE063) | s.k(0xE064) << 8, int(press is not None)))
    if (2, 1) in stage_start or (not LOOP and (1, 3) in stage_start): break

# per-stage figures: from each stage's first tick in play to the next's
stages = {}
def evenness(fl):
    rate = [(b[1] - a[1]) / (b[0] - a[0]) for a, b in zip(fl, fl[1:]) if a[1] is not None and b[1] is not None and b[0] > a[0]]
    return round(statistics.pstdev(rate) / statistics.mean(rate), 3) if len(rate) > 1 else None
def worst_second(fa, fb):
    """The fewest screens in any 50 frames from fa to fb (the spikes the
    averages hide)."""
    fr = [x[0] for x in flips if fa <= x[0] < fb]
    if fb - fa < 50: return None
    j = 0; best = None
    for st in range(fa, fb - 49):
        while j < len(fr) and fr[j] < st: j += 1
        k = j
        while k < len(fr) and fr[k] < st + 50: k += 1
        n = k - j; best = n if best is None else min(best, n)
    return best
ks = sorted(k for k in stage_start if k[1] > 0)
for a, b in zip(ks, ks[1:]):
    (fa, ta), (fb, tb) = stage_start[a], stage_start[b]
    fl = [x for x in flips if fa <= x[0] < fb]
    adv = collections.Counter(q[1] - p[1] for p, q in zip(fl, fl[1:]) if p[1] is not None and q[1] is not None)
    stages[a[1]] = dict(seconds=round((fb - fa) / 50, 1), ticks_per_s=round((tb - ta) / ((fb - fa) / 50), 2),
                        screens_per_s=round(len(fl) / ((fb - fa) / 50), 2), motion_cv=evenness(fl),
                        ticks_per_screen=dict(sorted(adv.items())),
                        gaps=dict(sorted(collections.Counter(q[0] - p[0] for p, q in zip(fl, fl[1:])).items())),
                        long_gaps=sum(1 for p, q in zip(fl, fl[1:]) if q[0] - p[0] >= 4),
                        worst_s=worst_second(fa, fb))
f0 = stage_start[ks[0]][0] if ks else 0
fl = [x for x in flips if x[0] >= f0]
gaps = collections.Counter(b[0] - a[0] for a, b in zip(fl, fl[1:]))
adv = collections.Counter(b[1] - a[1] for a, b in zip(fl, fl[1:]) if a[1] is not None and b[1] is not None)
rate = [(b[1] - a[1]) / (b[0] - a[0]) for a, b in zip(fl, fl[1:]) if a[1] is not None and b[1] is not None and b[0] > a[0]]
res = dict(sna=SNA, stages=stages,
           gaps=dict(sorted(gaps.items())), ticks_per_screen=dict(sorted(adv.items())),
           motion_cv=round(statistics.pstdev(rate) / statistics.mean(rate), 3) if rate else None,
           lag_n=len(lag), lag_mean=round(statistics.mean(lag), 2) if lag else None,
           lag_median=round(statistics.median(lag), 2) if lag else None,
           lag_p90=round(sorted(lag)[int(len(lag) * 0.9)], 2) if lag else None)
json.dump(res, open(OUT, 'w'), indent=1)
import pickle; pickle.dump(dict(OL=OL, FRAMES=FRAMES, TL=TL, flips=flips, lag=lag, stage_start=stage_start), open(OUT + '.tl.pkl', 'wb'))
print(json.dumps(res))
