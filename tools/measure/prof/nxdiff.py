"""The Next build against 1.1.3N: every differing byte must lie in a hole (the 128K renderer left out)."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, re
REF = (_SCRATCH + '/work/ref113n'); NEW = sys.argv[1]; NEX = sys.argv[2]
def syms(p):
    s = {}
    for l in open(p):
        m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
        if m: s[m.group(1)] = int(m.group(2), 16) & 0xFFFF
    return s
r = syms(REF + '/nemesis_next.sym'); n = syms(NEW + '/nemesis_next.sym')
# symbols: every symbol of the new build is where it was
moved = [(k, r[k], n[k]) for k in n if k in r and r[k] != n[k] and k != 'draw_sprites']
gone = sorted(k for k in r if k not in n and '.' not in k)
print('symbols: %d in 1.1.3N, %d now; moved: %d; gone (top level): %d' % (len(r), len(n), len(moved), len(gone)))
if moved: print('  MOVED:', moved[:10])
print('  gone:', ' '.join(gone))
# holes, as address ranges (1.1.3N symbols)
HOLES = [('fixed', r['edge_pat'], 0x7BF8), ('fixed', r['star_update'], r['star_reset']), ('fixed', r['star_rebuild'], r['invalidate_tile']),
         ('fixed', r['render_frame'], r['stars_moved']), ('fixed', r['draw_stars'], r['nl_buf']), ('fixed', r['spr_patsel'], r['star_l']),
         ('bank7', r['spr_colour'], r['page_7_end'])]
for kind, a, b in HOLES: print('  hole %s %04X-%04X %4d bytes' % (kind, a, b - 1, b - a))
print('  holes in all: %d bytes' % sum(b - a for k, a, b in HOLES))
# snapshots: 48K .sna header 27, then 4000-FFFF (banks 5, 2, paged), then 4 bytes, then the other banks in order
def sna_banks(p):
    d = open(p, 'rb').read(); port = d[49181]; cur = port & 7
    banks = {5: d[27:27 + 16384], 2: d[27 + 16384:27 + 32768], cur: d[27 + 32768:27 + 49152]}
    rest = d[49183:]; i = 0
    for b in range(8):
        if b in banks: continue
        banks[b] = rest[i:i + 16384]; i += 16384
    assert len(d) == 49183 + 5 * 16384, len(d)
    return banks, d[:27], d[49179:49183]
rb, rh, rt = sna_banks(REF + '/nemesis_next.sna'); nb, nh, nt = sna_banks(NEW + '/nemesis_next.sna')
print('snapshot header and tail equal:', rh == nh and rt == nt)
bad = 0; inhole = 0
for b in range(8):
    base = {5: 0x4000, 2: 0x8000}.get(b, 0xC000)
    for i in range(16384):
        if rb[b][i] != nb[b][i]:
            a = base + i
            ok = any((kind == 'bank7') == (b == 7) and (kind == 'bank7' or b in (5, 2)) and lo <= a < hi for kind, lo, hi in HOLES)
            if ok: inhole += 1
            else:
                bad += 1
                if bad <= 10: print('  OUTSIDE A HOLE: bank %d %04X: %02X -> %02X' % (b, a, rb[b][i], nb[b][i]))
print('snapshot bytes that differ: %d in the holes, %d outside' % (inhole, bad))
for f in ('nx_low.bin', 'nx_tur.bin', 'nx_gfx.dat'):
    print('%s identical: %s' % (f, open(REF + '/' + f, 'rb').read() == open(NEW + '/' + f, 'rb').read()))
a = open(REF + '/out.nex', 'rb').read(); b = open(NEX, 'rb').read()
d = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
print('.nex: %d and %d bytes; %d differ' % (len(a), len(b), len(d)))
