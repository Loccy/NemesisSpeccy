"""Static reachability over Konami's banks 0-3, from the relocator's item
list: what Konami's code and data can reach, following calls, jumps, the
dispatch tables and the port's patches (reloc/gen.py).  Used by the 48K's
keep lists (keep1.py, keepN.py, keepC.py, tabread.py; keep48.sh runs them)."""
import os, sys, bisect, collections
os.environ['NEM_TARGET'] = 'spec'
NEMROOT = os.environ.get('NEM_ROOT') or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))     # (the repository)
sys.path.insert(0, NEMROOT + '/reloc')
import gen
from listing import parse
rom = open(NEMROOT + '/nem.rom', 'rb').read()
ORG = {0: 0x4000, 1: 0x6000, 2: 0x8000, 3: 0xA000}
B = (0, 1, 2, 3)
items = {}; labels = {}; raw = {}; starts = {}; idx = {}
for b in B:
    it, lab, r = parse(b, rom)
    items[b] = it; raw[b] = r; starts[b] = [i[0] for i in it]
    labels[b] = {a: n for n, a in lab.items() if a is not None and ORG[b] <= a < ORG[b] + 0x2000}
    idx[b] = {i[0]: k for k, i in enumerate(it)}
def dbank(v): return gen.default_bank(v)
def item_at(b, v):
    st = starts[b]; k = bisect.bisect_right(st, v) - 1
    return k
def by(b, it): return raw[b][it[0] - ORG[b]:it[0] - ORG[b] + it[1]]
code_ptrs = {}
for e in gen.CODE_PTRS:
    b, a, n = e[:3]; stride = e[3] if len(e) > 3 else 2; cfg = e[4] if len(e) > 4 else None
    if b in B:
        for i in range(n): code_ptrs[(b, a + i * stride)] = cfg
def notptr(b, a): return any(nb == b and lo <= a < hi for nb, lo, hi in gen.NOT_PTR_RANGES)
DISP = 0x4067
# inline dispatch tables: call despachador followed by defw items
tables = {}      # (b, call addr) -> [(word addr, target)]
for b in B:
    its = items[b]
    for k, it in enumerate(its):
        if it[2] == 'code':
            bs = by(b, it)
            if bs[0] == 0xCD and len(bs) == 3 and (bs[1] | bs[2] << 8) == DISP:
                ws = []; j = k + 1
                while j < len(its) and its[j][2] in ('defw',):
                    d = by(b, its[j])
                    for i in range(0, len(d), 2): ws.append((its[j][0] + i, d[i] | d[i + 1] << 8))
                    j += 1
                    if its[j][0] in labels[b] and not labels[b][its[j][0]].startswith('L_') and False: break
                tables[(b, it[0])] = ws
def refs(b, k, removed):
    """Targets (bank, addr, how) of item k of bank b."""
    it = items[b][k]; a, n, kind = it[0], it[1], it[2]
    out = []
    if gen.left_out(b, a): return out, True
    bs = by(b, it)
    if kind == 'code':
        patch = gen.SPEC_PATCH.get((b, a))
        if patch is not None:
            # the port's replacement: follow any m<bank>_<addr> it names; falls through unless a jp/ret
            import re
            term = False
            for l in patch:
                for m in re.finditer(r'm(\d)_([0-9A-F]{4})', l): out.append((int(m.group(1)), int(m.group(2), 16), 'patch'))
                if l.strip().startswith(('jp ', 'ret')) and ',' not in l: term = True
            return out, term
        op = bs[0]; opk = it[5]
        term = op in (0xC9, 0xC3, 0x18, 0xE9) or (op in (0xDD, 0xFD) and bs[1] == 0xE9) or (op == 0xED and bs[1] in (0x4D, 0x45))
        if op in (0x10, 0x18, 0x20, 0x28, 0x30, 0x38):
            d = bs[1] - 256 if bs[1] > 127 else bs[1]; t = a + 2 + d
            tb = b if ORG[b] <= t < ORG[b] + 0x2000 else dbank(t)
            out.append((tb, t, 'jr'))
        elif opk in ('jp16', 'call16'):
            v = bs[-2] | bs[-1] << 8
            if v == DISP and (b, a) in tables:
                out.append((0, DISP, 'call'))
                for wa, t in tables[(b, a)]:
                    if (b, wa) in removed: continue
                    if 0x4000 <= t < 0xC000: out.append((dbank(t), t, 'disp'))
                return out, True
            if 0x4000 <= v < 0xC000: out.append((dbank(v), v, 'call'))
        elif opk == 'abs16':
            v = bs[-2] | bs[-1] << 8
            if 0x4000 <= v < 0xC000 and v not in (0x6000, 0x8000, 0xA000):
                tb = gen.SITE_BANK.get(a, dbank(v))
                if tb in B: out.append((tb, v, 'data'))
        elif opk == 'imm16':
            v = bs[-2] | bs[-1] << 8
            if 0x4000 <= v < 0xC000 and a not in gen.CONST_IMM and a not in getattr(gen, 'UNPLACED_IMM', ()) and a not in gen.IMM_SYMBOL:
                tb = gen.SITE_BANK.get(a, dbank(v))
                if tb in B: out.append((tb, v, 'imm'))
        return out, term
    # data
    if any((b, x) in code_ptrs for x in range(a, a + n)):
        for i in range(n - 1):
            if (b, a + i) in code_ptrs and (b, a + i) not in removed:
                v = bs[i] | bs[i + 1] << 8
                cfg = code_ptrs[(b, a + i)]
                if cfg is None and 0x4000 <= v < 0xC000: out.append((dbank(v), v, 'tab'))
        return out, False
    if kind == 'defw' and not notptr(b, a):
        ann = '->' in it[4]
        for i in range(0, n, 2):
            if (b, a + i) in removed: continue
            v = bs[i] | bs[i + 1] << 8
            if 0x4000 <= v < 0xC000 and (ann or v in labels[dbank(v)]): out.append((dbank(v), v, 'dw'))
    return out, False
def block_end(b, k):
    """Data: the items from k to the next label or code item."""
    its = items[b]; j = k + 1
    while j < len(its) and its[j][2] != 'code' and its[j][0] not in labels[b]: j += 1
    return j
def reach(roots, removed=frozenset()):
    seen = set(); work = []; odd = []
    def push(b, v, how):
        if b not in B: return
        k = item_at(b, v)
        it = items[b][k]
        if it[2] != 'code' and how in ('imm', 'data', 'tab', 'dw', 'patch'):
            for j in range(k, block_end(b, k)): work.append((b, j))
        else:
            if it[2] == 'code' and how in ('imm', 'data') and it[0] != v:
                odd.append((b, v, how))
            if it[2] == 'code' and how == 'imm':
                # a table base declared a few bytes before the table: take the next data block too
                its = items[b]; j = k
                while j < len(its) and its[j][0] < v + 16:
                    if its[j][2] != 'code':
                        for q in range(j, block_end(b, j)): work.append((b, q))
                        break
                    j += 1
            work.append((b, k))
    for b, v in roots_addr: push(b, v, 'call')
    while work:
        b, k = work.pop()
        if (b, k) in seen: continue
        seen.add((b, k))
        it = items[b][k]
        out, term = refs(b, k, removed)
        for tb, t, how in out: push(tb, t, how)
        if it[2] == 'code' and not term and not gen.left_out(b, it[0]) and k + 1 < len(items[b]):
            work.append((b, k + 1))
    return seen, odd
roots_addr = [(0, 0x4071), (0, 0x4028), (0, 0x4045), (0, 0x4054), (0, 0x49E9), (0, 0x5BD3)]
# what the platform's own code calls (m<bank>_<addr> in the port's sources)
import re, glob
plat = set()
for f in ['plat_spec.asm', 'native.asm', 'convert.asm', 'render.asm', 'pace.asm', 'ship.asm', 'star_check7.asm', 'spr_pmap.asm']:
    for l in open(NEMROOT + '/spec/' + f):
        l = l.split(';')[0]
        for m in re.finditer(r'\bm(\d)_([0-9A-F]{4})\b', l): plat.add((int(m.group(1)), int(m.group(2), 16)))
roots_addr += sorted(p for p in plat if p[0] in B)
def size(seen, kind=None, bank=None):
    s = 0
    for b, k in seen:
        it = items[b][k]
        if gen.left_out(b, it[0]): continue
        if bank is not None and b != bank: continue
        if kind == 'code' and it[2] != 'code': continue
        if kind == 'data' and it[2] == 'code': continue
        s += it[1]
    return s
if __name__ == '__main__':
    full, odd = reach(None)
    print('platform roots:', len(plat))
    tot = {b: sum(i[1] for i in items[b] if not gen.left_out(b, i[0])) for b in B}
    for b in B:
        print('bank %d: carried %5d  reachable code %5d data %5d  unreached %5d' % (b, tot[b], size(full, 'code', b), size(full, 'data', b), tot[b] - size(full, None, b)))
    print('all: carried %d reachable %d (code %d, data %d)' % (sum(tot.values()), size(full), size(full, 'code'), size(full, 'data')))
    print('odd refs into code:', len(odd), [('%d:%04X' % (b, v), h) for b, v, h in odd][:40])
    print('dispatch tables:')
    for (b, a), ws in sorted(tables.items()):
        print('  %d:%04X %2d entries  %s' % (b, a, len(ws), labels[b].get(a + 3, '')))
