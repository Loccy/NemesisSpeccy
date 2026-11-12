import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, re, pickle, collections, bisect
SPEC = (_NEM + '/spec')
raw = pickle.load(open(sys.argv[1], 'rb'))[sys.argv[2]]
want = sys.argv[3].split(',')
PAGES = {'PAGE_A': 0, 'PAGE_E': 1, 'PAGE_B': 3, 'PAGE_C': 4, 'PAGE_D': 6, 'PAGE_7': 7}
rows = []; cur = None; label = '?'; files = []
for l in open(SPEC + '/nemesis.lst', encoding='latin-1'):
    m = re.match(r'# file opened: (\S+)', l)
    if m: files.append(m.group(1)); continue
    if l.startswith('# file closed'): files.pop(); continue
    m = re.match(r'\s*(\d+)\+?\s*([0-9A-F]{4})( ~)?\s((?:[0-9A-F]{2} )*)\s*>?\s*(.*)$', l)
    if not m or m.group(3): continue
    a = int(m.group(2), 16); code = m.group(4).split(); text = m.group(5)
    pm = re.search(r'\bpage\s+(PAGE_\w+)', text)
    if pm and pm.group(1) in PAGES: cur = PAGES[pm.group(1)]
    lm = re.match(r'([A-Za-z_][\w.]*):', text)
    if lm and not lm.group(1).startswith('.'): label = lm.group(1)
    if code: rows.append((cur if a >= 0xC000 else -1, a, len(code), label, text.rstrip()))
tot = sum(raw.values())
for w in want:
    sel = [r for r in rows if r[3] == w]
    s = 0; out = []
    for pg, a, n, lab, text in sel:
        k = sum(raw.get((pg, a + i), 0) for i in range(n))
        s += k; out.append((k, a, text))
    print('== %s  %.1f%% of all time' % (w, 100 * s / tot))
    for k, a, text in out:
        print('%5.1f%% %04X  %s' % (100 * k / max(s, 1), a, text[:90]))
