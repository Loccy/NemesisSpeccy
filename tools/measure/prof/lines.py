"""Per-instruction counts within a label range: lines.py PKL START_LABEL END_LABEL [page] [per]"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, os, pickle, re, collections
sys.path.insert(0, (_NEM + '/spec'))
from skoolkit.traceutils import disassemble
D = pickle.load(open(sys.argv[1], 'rb'))
acc, cnt, events = D['acc'], D['cnt'], D['events']
syms = {}
for l in open(D['sym']):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
inv = collections.defaultdict(list)
for k, v in syms.items(): inv[v].append(k)
from emu import Spectrum
banks = Spectrum(D['sna']).mem.banks
def _a(x):
    return int(x[2:], 16) if x.startswith("0x") else syms[x]
a0 = _a(sys.argv[2]); a1 = _a(sys.argv[3]); page = int(sys.argv[4]) if len(sys.argv) > 4 else 0
ev = collections.Counter(e for e, t in events)
per = sys.argv[5] if len(sys.argv) > 5 else 'pm_tick'
n = ev[per]
mem = bytearray(65536)
mem[0x4000:0x8000] = banks[5]; mem[0x8000:0xC000] = banks[2]; mem[0xC000:] = banks[page]
tot = 0; a = a0
while a < a1:
    op, ln = disassemble(mem, a)[:2] if True else None
    key = a if a < 0xC000 else a | page << 16
    c = cnt.get(key, 0); t = acc.get(key, 0); tot += t
    labs = [k for k in inv.get(a, []) if not re.match(r'(?:[A-Z]_)?m\d+_', k) or len(inv[a]) == 1]
    for lb in labs: print('%s:' % lb)
    print('   %04X %-22s %9.2f x  %8.1f T' % (a, op, c / n, t / n))
    a += ln
print('total %.1f T per %s (%d)' % (tot / n, per, n))
