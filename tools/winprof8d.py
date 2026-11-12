import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, re, json, bisect, collections
sys.path.insert(0, (_NEM + '/spec'))
import emu
from emu import Spectrum
SPEC = (_NEM + '/spec')
PAGES = {'PAGE_A': 0, 'PAGE_E': 1, 'PAGE_B': 3, 'PAGE_C': 4, 'PAGE_D': 6, 'PAGE_7': 7}
# map (page, address) -> (file, label) from the listing
files = []; cur_page = None; label = '?'
table = collections.defaultdict(list)
for l in open(SPEC + '/nemesis.lst', encoding='latin-1'):
    m = re.match(r'# file opened: (\S+)', l)
    if m: files.append(m.group(1)); continue
    if l.startswith('# file closed'): files.pop(); continue
    m = re.match(r'\s*\d+\+?\s*([0-9A-F]{4})( ~)?\s((?:[0-9A-F]{2} )*)\s*>?\s*(.*)$', l)
    if not m or m.group(2): continue
    addr = int(m.group(1), 16); code = m.group(3).strip(); text = m.group(4)
    pm = re.search(r'\bpage\s+(PAGE_\w+)', text)
    if pm and pm.group(1) in PAGES: cur_page = PAGES[pm.group(1)]
    lm = re.match(r'([A-Za-z_][\w.]*):', text)
    if lm and not lm.group(1).startswith('.'): label = lm.group(1)
    elif lm: label = label.split('.')[0] + lm.group(1)
    if code:
        key = cur_page if addr >= 0xC000 else -1
        table[key].append((addr, files[-1] if files else '?', label))
for k in table: table[k].sort()
idx = {k: [a for a, f, l in v] for k, v in table.items()}
def where(pc, page):
    key = page if pc >= 0xC000 else -1
    if key not in table: return ('page%d?' % page, '?')
    i = bisect.bisect_right(idx[key], pc) - 1
    if i < 0: return ('?', '?')
    a, f, l = table[key][i]; return (f, l)
SNA, SYM = sys.argv[1], sys.argv[2]
WIN = {'dissolve': (1615, 1621)}
s = Spectrum(SNA); sy = emu._syms(SYM); s.syms = sy

regs = s.regs; FR = 70908; STEP = 997
def keys(f):
    kb = [0] * 8
    fire = (f // 25) % 4 == 0
    if fire: kb[7] |= 1
    return kb
raw = {w: collections.Counter() for w in WIN}; res = {w: collections.Counter() for w in WIN}; ticks = {w: 0 for w in WIN}; last = s.k(0xE003)
played = 0
while played < 1621 * 50:
    w = next((n for n, (a, b) in WIN.items() if a * 50 <= played < b * 50), None) if s.k(0xE000) == 5 else None
    if w is None:
        s.run_frame(keys)
    else:
        s.hook(advance=True)
        s.tr.keyboard = keys(s.frame)
        end = s.t0 + (s.frame + 1) * FR
        pc = s.pc
        while regs[25] < end:
            s.sim.trace(pc, -1, 0, min(end, regs[25] + STEP), 1, None, None, None, None, None)
            pc = regs[24]
            pg = s.tr.out7ffd & 7; res[w][where(pc, pg)] += 1; raw[w][(pg if pc >= 0xC000 else -1, pc)] += 1
        s.pc = pc; s.frame += 1
    c = s.k(0xE003)
    if w: ticks[w] += (c - last) & 255
    last = c
    if s.k(0xE000) == 5: played += 1
out = {}
for w in WIN:
    n = sum(res[w].values()); secs = WIN[w][1] - WIN[w][0]
    byfile = collections.Counter()
    for (f, l), k in res[w].items(): byfile[f] += k
    out[w] = {'samples': n, 'ticks_per_s': ticks[w] / secs, 'by_file': {f: round(100 * k / n, 1) for f, k in byfile.most_common()},
              'top': [(f, l, round(100 * k / n, 1)) for (f, l), k in res[w].most_common(25)]}
json.dump(out, open(sys.argv[3], 'w'), indent=1)
import pickle; pickle.dump(raw, open(sys.argv[3] + '.raw', 'wb'))
for w in WIN:
    print('==', w, 'ticks/s %.1f' % out[w]['ticks_per_s'])
    print('   by file:', ', '.join('%s %s%%' % (f, p) for f, p in list(out[w]['by_file'].items())[:9]))
