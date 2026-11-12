"""Who calls a routine: executed CALL/JP instructions whose operand is the target, with counts per tick."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, os, pickle, re, bisect, collections
sys.path.insert(0, (_NEM + '/spec'))
D = pickle.load(open(sys.argv[1], "rb")); targets = sys.argv[2:]
if "events" not in D: D["events"] = [("pm_tick", 0)] * D["cnt"][[int(l.split("0x")[1], 16) & 0xFFFF for l in open(D["sym"]) if l.startswith("pm_tick:")][0]]
cnt, events = D['cnt'], D['events']
syms = {}
for l in open(D['sym']):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
from emu import Spectrum
banks = Spectrum(D['sna']).mem.banks
def rd(pc, page):
    if pc < 0x4000: return 0
    if pc < 0x8000: return banks[5][pc-0x4000]
    if pc < 0xC000: return banks[2][pc-0x8000]
    return banks[page][pc-0xC000]
ticks = sum(1 for e, t in events if e == 'pm_tick')
inv = collections.defaultdict(list)
for k, v in syms.items(): inv[v].append(k)
allv = sorted(set(v for k, v in syms.items() if '.' not in k and not re.match(r'(?:[A-Z]_)?m\d+_[0-9A-F]{4}$', k)))
def near(pc):
    i = bisect.bisect_right(allv, pc) - 1; a = allv[i]
    return '%s+%d' % ([k for k in inv[a] if '.' not in k][0], pc - a)
OPS = {0xCD: 'call', 0xC3: 'jp', 0xC4: 'call nz', 0xCC: 'call z', 0xD4: 'call nc', 0xDC: 'call c', 0xC2: 'jp nz', 0xCA: 'jp z', 0xD2: 'jp nc', 0xDA: 'jp c', 0xFA: 'jp m', 0xF2: 'jp p'}
for tg in targets:
    ta = syms[tg]; rows = []
    for key, n in cnt.items():
        pc = key & 0xFFFF; pg = key >> 16
        op = rd(pc, pg)
        if op in OPS and (rd(pc+1, pg) | rd(pc+2, pg) << 8) == ta:
            lab = [k for k in inv.get(pc, []) if True]
            rows.append((n, pc, pg, OPS[op], lab[0] if lab else near(pc)))
    ent = sum(n for key, n in cnt.items() if (key & 0xFFFF) == ta)
    print('%s: entered %.2f a tick' % (tg, ent / ticks))
    for n, pc, pg, op, lab in sorted(rows, reverse=True)[:40]:
        print('   %7.2f  %04X pg%d  %-8s %s' % (n / ticks, pc, pg, op, lab))
