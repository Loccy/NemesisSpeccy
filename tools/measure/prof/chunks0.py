"""Konami's bank 0 code as chunks that end in an unconditional transfer
(what HOT_CLONES can copy), by time per byte.  chunks0.py PROFILE.pkl [BUDGET]"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, os, pickle, re, collections
sys.path.insert(0, (_NEM + '/reloc')); os.environ['NEM_TARGET'] = 'spec'
import gen as G
D = pickle.load(open(sys.argv[1], 'rb')); acc, cnt = D['acc'], D['cnt']
BUDGET = int(sys.argv[2]) if len(sys.argv) > 2 else 1208
syms = {}
for l in open(D['sym']):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
ticks = cnt[syms['pm_tick']]
g = G.Gen(open((_NEM + '/nem.rom'), 'rb').read())
items = [it for it in g.items[0] if g.home.get((0, it[0])) == 'fixed' and ('m0_%04X' % it[0]) in syms]
raw = g.raw[0]; org = G.ORG[0]
TERM = (0xC9, 0xC3, 0x18, 0xE9)
def addr(it): return syms['m0_%04X' % it[0]]
ends = {}
for i, it in enumerate(items):
    nxt = addr(items[i + 1]) if i + 1 < len(items) else syms['section_fixed_end']
    ends[it[0]] = nxt
def t_of(it): return sum(acc.get(x, 0) for x in range(addr(it), ends[it[0]]))
chunks = []; cur = []
for it in items:
    if it[2] != 'code' and not cur: continue          # data between routines
    cur.append(it)
    if it[2] == 'code' and raw[it[0] - org] in TERM:
        chunks.append(cur); cur = []
tot = sum(t_of(it) for it in items)
C = []
for ch in chunks:
    n = ends[ch[-1][0]] - addr(ch[0]); t = sum(t_of(it) for it in ch)
    C.append(dict(lo=ch[0][0], hi=ch[-1][0] + ch[-1][1] - 1, n=n, t=t, data=sum(1 for it in ch if it[2] != 'code')))
print('bank 0: %d T a tick in %d chunks, %d bytes of code in chunks' % (tot / ticks, len(C), sum(c['n'] for c in C)))
C.sort(key=lambda c: -c['t'] / c['n'])
cb = ct = 0; pick = []
for c in C:
    if c['t'] / ticks < 5: break
    cb += c['n']; ct += c['t']
    mark = ''
    if cb <= BUDGET: pick.append(c); mark = '*'
    print('%s %04X-%04X %4d bytes %6.0f T/tick %6.1f T/tick/byte  cum %5d bytes %5.1f%%%s' % (mark or ' ', c['lo'], c['hi'], c['n'], c['t'] / ticks, c['t'] / ticks / c['n'], cb, 100 * ct / tot, '  (data in it)' if c['data'] else ''))
pickle.dump(dict(C=C, ticks=ticks, tot=tot), open((_SCRATCH + '/work/chunks0.pkl'), 'wb'))
