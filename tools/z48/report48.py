"""Report on census48.py's runs: what each stage runs and reads of Konami's
banks 0-3, at three levels (the instructions themselves; the whole routines
and tables they belong to; what is statically reachable given the object
types, bosses and stage endings the stage used), and the data banks."""
import pickle, zlib, sys, collections
from reach import *
SIZE = 16 * 8192
def OR(a, b): return bytearray((int.from_bytes(a, 'little') | int.from_bytes(b, 'little')).to_bytes(SIZE, 'little'))
EX = {}; RD = {}; DISP = collections.defaultdict(set); TICKS = collections.Counter()
for p in [a for a in sys.argv[1:] if a.endswith('.pkl')]:
    d = pickle.load(open(p, 'rb'))
    for k, z in d['ex'].items():
        a = bytearray(zlib.decompress(z)); EX[k] = OR(EX[k], a) if k in EX else a
    for k, z in d['rd'].items():
        a = bytearray(zlib.decompress(z)); RD[k] = OR(RD[k], a) if k in RD else a
    for k, v in d['disp'].items(): DISP[k] |= set(v)
    for k, v in d['ticks'].items(): TICKS[k] += v
    print(p, 'stages:', [(t, s, st) for t, s, st in d['stages']][:40], 'deaths:', len(d['deaths']))
print('ticks by (state, stage):')
for k in sorted(TICKS): print('   state %d stage %2d: %6d' % (k + (TICKS[k],)))

# ---- routines (code) and blocks (data) of banks 0-3 --------------------------
def is_term(b, it):
    bs = by(b, it); op = bs[0]
    if op in (0xC9, 0xC3, 0x18, 0xE9) or (op in (0xDD, 0xFD) and bs[1] == 0xE9) or (op == 0xED and bs[1] in (0x4D, 0x45)): return True
    return op == 0xCD and len(bs) == 3 and (bs[1] | bs[2] << 8) == 0x4067
grp = {}; gsize = collections.Counter(); gkind = {}; gname = {}
for b in B:
    g = None; prev = None
    for k, it in enumerate(items[b]):
        code = it[2] == 'code'
        lab = labels[b].get(it[0])
        new = prev is None or (code != (prev[2] == 'code'))
        if code:
            if lab and not lab.startswith('L_'): new = True
            if prev is not None and prev[2] == 'code' and is_term(b, prev): new = True
        else:
            if lab: new = True
        if new: g = (b, it[0]); gkind[g] = 'code' if code else 'data'
        grp[(b, k)] = g
        if not gen.left_out(b, it[0]): gsize[g] += it[1]
        prev = it
def named(b, a):
    c = [x for x in labels[b] if x <= a and not labels[b][x].startswith('L_')]
    return labels[b][max(c)] if c else '?'
def items_of(m, want_code):
    """Items of banks 0-3 marked in a map: executed starts, or bytes read of data items."""
    out = set(); odd = 0
    for b in B:
        base = b << 13
        for off in range(8192):
            if m[base + off]:
                a = ORG[b] + off
                if want_code:
                    k = idx[b].get(a)
                    if k is None or items[b][k][2] != 'code': odd += 1
                    else: out.add((b, k))
                else:
                    k = item_at(b, a)
                    if items[b][k][2] != 'code': out.add((b, k, a))
    return out, odd
def nl(s): return {x for x in s if not gen.left_out(x[0], items[x[0]][x[1]][0])}

PLAY = (4, 5, 6, 7)
def stage_maps(s, states=PLAY):
    ex = bytearray(SIZE); rd = bytearray(SIZE)
    for k in EX:
        if k[1] == s and k[0] in states: ex = OR(ex, EX[k]); rd = OR(rd, RD[k])
    return ex, rd
T1 = tables[(0, 0x5DFA)]; T2 = tables[(1, 0x6B43)]; ST = tables[(1, 0x6CD4)]
BT = [tables[(1, 0x7C3E)], tables[(1, 0x7C62)], tables[(1, 0x7C7C)]]
STT = tables[(0, 0x52C4)]; EXP = tables[(0, 0x4AC7)]
SEL = {(0, 0x5DFD): (0, T1), (1, 0x6B46): (1, T2), (1, 0x6CD7): (1, ST), (1, 0x7C41): (1, BT[0]), (1, 0x7C65): (1, BT[1]),
       (1, 0x7C7F): (1, BT[2]), (0, 0x52C7): (0, STT), (0, 0x4ACA): (0, EXP)}
ALLTAB = {(b, a + 3): (b, ws) for (b, a), ws in tables.items()}
def used(s, states=PLAY):
    u = collections.defaultdict(set)
    for k, v in DISP.items():
        if k[1] == s and k[0] in states:
            for b, ret, a in v: u[(b, ret)].add(a)
    return u
def removed_for(u, tabs):
    rem = set()
    for key, (b, ws) in tabs.items():
        for i, (wa, t) in enumerate(ws):
            if i not in u.get(key, ()): rem.add((b, wa))
    return frozenset(rem)
full, _ = reach(None)
everex = bytearray(SIZE)
for k in EX: everex = OR(everex, EX[k])
ever_items, odd = items_of(everex, True)
ever_groups = {grp[x] for x in ever_items}
print('\nexecuted anywhere in the runs: %d instructions, %d bytes; whole routines %d bytes; not at an instruction of the listing: %d' % (
    len(ever_items), sum(items[b][k][1] for b, k in nl(ever_items)), sum(gsize[g] for g in ever_groups), odd))
print('statically reachable: %d; of its code, in routines never run in these runs: %d bytes' % (
    size(full), sum(gsize[g] for g in {grp[x] for x in full if items[x[0]][x[1]][2] == 'code'} - ever_groups)))
res = {}
print('\nstage  ticks | instr bytes  routines  data read  tables | run+read  whole  | static(types,bosses,endings)  of it: run here / run elsewhere / never run | types bosses')
STAGES = [s for s in range(1, 13) if any(k[1] == s and k[0] in PLAY for k in EX)]
for s in STAGES:
    ex, rd = stage_maps(s)
    xi, odd = items_of(ex, True); xi = nl(xi)
    xg = {grp[x] for x in xi}
    di, _ = items_of(rd, False); di = {x for x in di if not gen.left_out(x[0], x[2])}
    dg = {grp[(b, k)] for b, k, a in di}
    ib = sum(items[b][k][1] for b, k in xi); rb = sum(gsize[g] for g in xg); db = len(di); tb = sum(gsize[g] for g in dg)
    u = used(s)
    r, _ = reach(None, removed_for(u, SEL))
    rc = {x for x in r if items[x[0]][x[1]][2] == 'code' and not gen.left_out(x[0], items[x[0]][x[1]][0])}
    rgs = {grp[x] for x in rc}
    here = sum(gsize[g] for g in rgs & xg); other = sum(gsize[g] for g in (rgs - xg) & ever_groups); never = sum(gsize[g] for g in rgs - xg - ever_groups)
    types = sorted(a + 1 for a in u.get((0, 0x5DFD), ())); bosses = sorted(set(u.get((1, 0x7C41), ())) | set(u.get((1, 0x7C65), ())) | set(u.get((1, 0x7C7F), ())))
    n = sum(TICKS[(st, s)] for st in PLAY)
    res[s] = dict(ticks=n, instr=ib, routines=rb, data=db, tables=tb, static=size(r), static_code=size(r, 'code'), static_data=size(r, 'data'),
                  here=here, other=other, never=never, types=types, bosses=bosses, xg=xg, dg=dg, r=r, u=u, ex=ex, rd=rd)
    print('%5d %6d | %11d %9d %10d %7d | %8d %6d | %6d (code %5d data %4d)  %5d / %5d / %5d | %s  %s' % (
        s, n, ib, rb, db, tb, ib + db, rb + tb, size(r), size(r, 'code'), size(r, 'data'), here, other, never,
        ' '.join('%02X' % t for t in types), bosses))
# what every stage 1-8 runs, and the union
S8 = [s for s in STAGES if s <= 8]
common = set.intersection(*[res[s]['xg'] for s in S8]); union = set.union(*[res[s]['xg'] for s in STAGES])
print('\nroutines run in every stage 1-8: %d bytes; in any stage: %d bytes' % (sum(gsize[g] for g in common), sum(gsize[g] for g in union)))
dcommon = set.intersection(*[res[s]['dg'] for s in S8]); dunion = set.union(*[res[s]['dg'] for s in STAGES])
print('tables read in every stage 1-8: %d bytes; in any stage: %d bytes' % (sum(gsize[g] for g in dcommon), sum(gsize[g] for g in dunion)))
# the front end and the ending
for nm, sts, sg in (('front end (states 0-3)', (0, 1, 2, 3), None),):
    ex = bytearray(SIZE)
    for k in EX:
        if k[0] in sts: ex = OR(ex, EX[k])
    xi, _ = items_of(ex, True); xg = {grp[x] for x in nl(xi)}
    print('%s: routines %d bytes, of which not run in any stage: %d' % (nm, sum(gsize[g] for g in xg), sum(gsize[g] for g in xg - union)))
# data banks
print('\nbytes read of the data banks, by stage (states 4-7):')
print('stage ' + ''.join('  bank%-3d' % b for b in (4, 5, 6, 9, 10, 11, 12)) + '   pieces(bank 11 below 97DE)/16')
for s in STAGES:
    rd = res[s]['rd']
    row = [sum(rd[(b << 13):(b << 13) + 8192]) for b in (4, 5, 6, 9, 10, 11, 12)]
    pieces = len({off >> 4 for off in range(0x17DE) if rd[(11 << 13) + off]})
    print('%5d ' % s + ''.join('%9d' % x for x in row) + '   %d pieces' % pieces)
pickle.dump({s: {k: v for k, v in res[s].items() if k not in ('ex', 'rd')} for s in res}, open('report48.pkl', 'wb'))
