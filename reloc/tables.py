"""Audit word tables read through dame_palabra (0x47AE) / renglon_del_guion (0x9100):
for each base, show the DATA block and its words, and whether gen relocates them."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import re, sys
import gen as G
from listing import parse
rom = open(NEM_ROOT + '/nem.rom', 'rb').read()
SRC = NEM_ROOT + '/ref/Nemesis-disassembly/src/nemesis_p%02d.asm'
def blocks(b):
    out = []
    for m in re.finditer(r'; DATOS ([^:]+):.*?\n;\s+0x([0-9a-f]+)\.\.0x([0-9a-f]+)', open(SRC % b, encoding='latin1').read(), re.S):
        out.append((int(m.group(2), 16), int(m.group(3), 16), m.group(1)))
    return out
g = G.Gen(rom); g.generate('/tmp/claude-0/-home-claude/23339f3b-0574-50a0-95e8-9ed402c44efa/scratchpad/x.asm')
bases = []
for b in (0, 1, 2, 3):
    L = open(SRC % b, encoding='latin1').read().split('\n')
    for i, l in enumerate(L):
        if re.search(r'call (047aeh|09100h|dame_palabra|renglon_del_guion)', l):
            for k in range(i - 1, max(0, i - 7), -1):
                m = re.search(r'ld hl,0([0-9a-f]{4})h', L[k])
                if m: bases.append((b, int(m.group(1), 16), L[k].split(';')[-1].strip()[:60])); break
B = {b: blocks(b) for b in range(13)}
def bank_of(v, site_bank):
    return G.default_bank(v)
for sb, t, cm in sorted(set(bases)):
    vb = G.default_bank(t)
    if sb == 0 and t >= 0x6000: vb = G.SITE_BANK.get(None, vb)
    org = {0: 0x4000, 1: 0x6000, 2: 0x8000, 3: 0xA000}.get(vb)
    blk = [x for x in B.get(vb, []) if x[0] <= t + 2 < x[1]]
    if not blk or org is None:
        print('%d %04X: no block (%s)' % (sb, t, cm)); continue
    lo, hi, name = blk[0]
    ws = []
    for a in range(max(lo, t), min(hi, t + 64), 2):
        if a + 1 >= hi: break
        if (a - t) % 2: continue
        v = rom[vb * 8192 + a - org] | rom[vb * 8192 + a - org + 1] << 8
        ws.append('%04X%s' % (v, '*' if (vb, a) in g.reloc_words else ''))
    print('%d %04X [bank %d %s %04X-%04X] %s' % (sb, t, vb, name, lo, hi, ' '.join(ws)))
