import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, pickle, re, json, collections, bisect
sys.path.insert(0, (_NEM + '/spec'))
import test_convert as tc
lines = []; files = []; cur = None
PAGES = {'PAGE_A': 0, 'PAGE_E': 1, 'PAGE_B': 3, 'PAGE_C': 4, 'PAGE_D': 6, 'PAGE_7': 7}
for l in open((_NEM + '/spec/nemesis.lst'), encoding='latin-1'):
    m = re.match(r'# file opened: (\S+)', l)
    if m: files.append(m.group(1)); continue
    if l.startswith('# file closed'): files.pop(); continue
    m = re.match(r'\s*\d+\+?\s*([0-9A-F]{4})( ~)?\s((?:[0-9A-F]{2} )*)\s*>?\s*(.*)$', l)
    if not m or m.group(2): continue
    a = int(m.group(1), 16); text = m.group(4)
    pm = re.search(r'\bpage\s+(PAGE_\w+)', text)
    if pm and pm.group(1) in PAGES: cur = PAGES[pm.group(1)]
    if cur == 3 and a >= 0xC000: lines.append((a, text))
lines.sort(); addrs = [a for a, t in lines]
lab = []; curl = '?'
for a, t in lines:
    lm = re.match(r'(\.?[A-Za-z_]\w*):', t)
    if lm: curl = lm.group(1)
    lab.append(curl)
sim = tc.sim; r = tc.r; mem = tc.mem
cost = collections.Counter()
def run(rows):
    for i, (p, c) in enumerate(rows):
        mem[tc.syms['cv_pat'] + i] = p; mem[tc.syms['cv_col'] + i] = c
    sp = 0xAEA0; mem[sp] = 0xFE; mem[sp + 1] = 0xFF; mem[0xFFFE] = 0x18; mem[0xFFFF] = 0xFE
    r[12] = sp; r[24] = tc.syms['convert_tile']
    while r[24] != 0xFFFE:
        pc = r[24]; t = r[25]
        sim.opcodes[mem[pc]]()
        i = bisect.bisect_right(addrs, pc) - 1
        cost[lab[i] if i >= 0 else '?'] += r[25] - t
boss = [bytes.fromhex(x[0]) for x in json.load(open(sys.argv[1]))['boss']]
seen = set(); tot = 0
for b in boss:
    if b in seen: continue
    seen.add(b); run([(b[i], b[8 + i]) for i in range(8)])
T = sum(cost.values())
print('boss characters: %d distinct, mean %d T-states each' % (len(seen), T // len(seen)))
for l, t in cost.most_common(14): print('  %5.1f%%  %s' % (100 * t / T, l))
