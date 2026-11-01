"""On the MSX original, through a whole game: every read of a ROM bank the
Spectrum build does not carry whole (6, 9, 10, 13-15), with the window it
was seen through and the instructions that read it.
usage: bankreads.py CONFIG TICKS OUT.json   CONFIG as census.py"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, json, collections
sys.path.insert(0, NEM_ROOT + '/spec')
import lockstep_spec as LS
CONF, N, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3]
CALLS = {'none': [], 'hyper': [0xA0D8, 0xA110], 'idle': []}[CONF]
import os
WATCH = set(int(x) for x in os.environ.get('WATCH', '6,9,10,13,14,15').split(','))
def keys(t, started):
    if CONF == 'idle': return 0xFF, 0x3F                 # nobody at the keys: the attract cycle
    if not started: return (0xFE if (t % 40) < 4 else 0xFF), 0x3F
    return (0xFE if t % 8 < 4 else 0xFF), 0x3F
LS.keys_for_tick = keys
orig = LS.Orig(); orig.boot()
regs = orig.sim.registers; mem = orig.mem
reads = collections.defaultdict(set)      # bank -> offsets
pcs = collections.defaultdict(collections.Counter)
byreader = collections.defaultdict(set)     # (bank, reader pc) -> offsets
cls = type(mem); oget = cls.__getitem__
def gt(self, a):
    if 0x4000 <= a < 0xC000:
        w = (a - 0x4000) >> 13; b = self.bank[w]
        if b in WATCH:
            reads[b].add(a & 0x1FFF); pcs[b][(regs[24], a & 0xE000)] += 1; byreader[(b, regs[24])].add(a & 0x1FFF)
    return oget(self, a)
cls.__getitem__ = gt
given = False; phases = set()
for i in range(N):
    LS.TICK[0] = i
    if mem[0xE000] == 5 and not given:
        for a in CALLS: LS.call_msx(orig, a)
        given = True
    LS.sync_tick(orig)
    phases.add(mem[0xE061])
    if i % 10000 == 0: print('tick', i, 'phase', mem[0xE061], flush=True)
out = {}
for b in sorted(reads):
    offs = sorted(reads[b]); runs = []; s = p = offs[0]
    for o in offs[1:]:
        if o != p + 1: runs.append((s, p)); s = o
        p = o
    runs.append((s, p))
    out[b] = {'bytes': len(offs), 'runs': ['%04X-%04X' % r for r in runs],
              'readers': ['%04X via %04X x%d' % (pc, w, n) for (pc, w), n in pcs[b].most_common(40)]}
for (b, pc), offs in byreader.items():
    out.setdefault(b, {}).setdefault('per_reader', {})['%04X' % pc] = [len(offs), min(offs), max(offs)]
json.dump(out, open(OUT, 'w'), indent=1)
print('phases', sorted(phases)); print(json.dumps({b: (v['bytes'], len(v['runs'])) for b, v in out.items()}))
