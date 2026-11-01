"""Census of Konami's writes into its map buffer (MSX ED00-EFFF) on the MSX
original (msxsim), with the ship invulnerable, weapons given through the
game's own cheat routines, the ship sweeping up and down and firing.  Lists
every instruction that wrote there, with counts and the stages seen.
usage: [TARGETS=1] census.py CONFIG TICKS OUT.json   CONFIG: none | hyper | double"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, json, collections
sys.path.insert(0, NEM_ROOT + '/spec')
import lockstep_spec as LS
CONF, N, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3]
TARGETS = _os.environ.get('TARGETS')   # TARGETS=1: the ship put on every hidden target (bonus stages)
CALLS = {'none': [], 'hyper': [0xA0D8, 0xA110], 'double': [0xA10B, 0xA106, 0xA110, 0xA110]}[CONF]
def keys(t, started):
    if not started: return (0xFE if (t % 40) < 4 else 0xFF), 0x3F
    row8 = 0xFF; joy = 0x3F
    if t % 8 < 4: row8 &= 0xFE
    ph = (t // 45) % 4
    if ph == 0: row8 &= ~0x20 & 0xFF; joy &= ~0x01        # up
    if ph == 2: row8 &= ~0x40 & 0xFF; joy &= ~0x02        # down
    return row8, joy
LS.keys_for_tick = keys
orig = LS.Orig(); orig.boot()
regs = orig.sim.registers; mem = orig.mem
hits = collections.defaultdict(lambda: [0, set()])
cls = type(mem); oset = cls.__setitem__
def st(self, a, v):
    if 0xED00 <= a < 0xF000:
        h = hits[regs[24]]; h[0] += 1; h[1].add(self.ram[0x2061])
    oset(self, a, v)
cls.__setitem__ = st
def call(addr):
    sp = (regs[12] - 2) & 0xFFFF
    oset(mem, sp, 0x54); oset(mem, sp + 1, 0x40); regs[12] = sp; regs[24] = addr
    ops = orig.sim.opcodes
    while regs[24] != 0x4054:
        ops[mem[regs[24]]](); regs[25] += 1
given = False; phases = set()
for i in range(N):
    LS.TICK[0] = i
    if mem[0xE000] == 5 and not given:
        for a in CALLS: call(a)
        given = True
    if TARGETS and mem[0xE000] == 5 and mem[0xE1C1]:      # the bonus stages: every target touched
        oset(mem, 0xE204, mem[0xE1C2]); oset(mem, 0xE206, mem[0xE1C3])
    LS.sync_tick(orig)
    phases.add(mem[0xE061])
    if i % 5000 == 0: print('tick', i, 'state', mem[0xE000], 'phase', mem[0xE061], flush=True)
json.dump({'%04X' % pc: [n, sorted(ph)] for pc, (n, ph) in hits.items()}, open(OUT, 'w'))
print('phases seen', sorted(phases), 'writers', len(hits))
