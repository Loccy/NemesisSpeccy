"""Census for the 48K question: on the MSX original (msxsim), over a scripted
game, by Konami's state and stage:
  * every instruction address run (by cartridge bank),
  * every cartridge byte read (by bank),
  * every use of Konami's dispatcher (0:4067): the table it was called
    with and the index.
The driver is the graphics census's (tools/native/census_gfx.py, since
removed from the repository): the same keys, cheat, targets, deaths and
game over, so the routes are the graphics census's.

usage: [TARGETS=1] [DEATHS=1] [GAMEOVER=1] [NOCHEAT=1] census48.py TICKS OUT.pkl
"""
import os, sys, pickle, collections, time, zlib
NEM = os.environ.get('NEM_ROOT') or os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, NEM + '/spec'); sys.path.insert(0, NEM + '/msxsim'); sys.path.insert(0, NEM + '/reloc')
sys.argv, _argv = ['x'], sys.argv
import lockstep_spec as LS
import msxsim
sys.argv = _argv
N, OUT = int(sys.argv[1]), sys.argv[2]
TARGETS = os.environ.get('TARGETS'); DEATHS = os.environ.get('DEATHS'); GAMEOVER = os.environ.get('GAMEOVER')
NOCHEAT = os.environ.get('NOCHEAT')
DEATH_AT = int(os.environ.get('DEATH_AT', '900'))

def keys(t, started):
    if not started: return (0xFE if (t % 40) < 4 else 0xFF), 0x3F
    row8 = 0xFF; joy = 0x3F
    if t % 8 < 4: row8 &= 0xFE
    ph = (t // 45) % 4
    if ph == 0: row8 &= ~0x20 & 0xFF; joy &= ~0x01
    if ph == 2: row8 &= ~0x40 & 0xFF; joy &= ~0x02
    return row8, joy
LS.keys_for_tick = keys

o = LS.Orig(); LS.patch_front_end(o); o.boot()
regs = o.sim.registers; mem = o.mem; ops = o.sim.opcodes; sim = o.sim
ram = mem.ram; bank = mem.bank
def K(a): return ram[a - 0xC000]

SIZE = 16 * 8192
EX = {}; RD = {}; DISP = collections.defaultdict(set); TICKS = collections.Counter()
C = [None, None, None]            # the current key's executed map, read map, key
def switch():
    k = (ram[0x2000], ram[0x2061])          # E000 the state, E061 the stage
    if k != C[2]:
        if k not in EX: EX[k] = bytearray(SIZE); RD[k] = bytearray(SIZE)
        C[0] = EX[k]; C[1] = RD[k]; C[2] = k
cls = type(mem); oset = cls.__setitem__; oget = cls.__getitem__
def st_hook(self, a, v):
    oset(self, a, v)
    if a == 0xE061 or a == 0xE000: switch()
def gt_hook(self, a):
    if 0x4000 <= a < 0xC000:
        C[1][(bank[(a - 0x4000) >> 13] << 13) | (a & 0x1FFF)] = 1
    return oget(self, a)
cls.__setitem__ = st_hook
cls.__getitem__ = gt_hook
switch()

def tick():
    started = False
    while True:
        pc = regs[24]
        if pc == 0x4054 and started:
            return
        if pc == 0x40DF and regs[26] and not started:
            o.vdp.status |= 0x80; o.int_pending = True; o.frames += 1
            sim.accept_interrupt(regs, mem, pc); started = True
            continue
        if pc < 0x4000:
            if pc not in msxsim.STUB_RANGE:
                raise msxsim.Unknown('execution at %04X' % pc)
        elif pc < 0xC000:
            C[0][(bank[(pc - 0x4000) >> 13] << 13) | (pc & 0x1FFF)] = 1
            if pc == 0x4067:
                sp = regs[12]
                ret = oget(mem, sp) | oget(mem, sp + 1) << 8
                DISP[C[2]].add((bank[(ret - 0x4000) >> 13], ret, regs[0]))
        ops[oget(mem, pc)]()
        regs[25] += 1

def call(addr):
    sp = (regs[12] - 2) & 0xFFFF
    oset(mem, sp, 0x54); oset(mem, sp + 1, 0x40); regs[12] = sp; regs[24] = addr
    while regs[24] != 0x4054:
        ops[oget(mem, regs[24])](); regs[25] += 1
def mortal(on):
    mem.rom[1 * 8192 + 0x75F0 - 0x6000] = 0x00 if on else 0xC9
mortal(False)
given = False; died = set(); lives_was = None; in_stage = 0; last_stage = None; deaths = []
stages_seen = []; t0 = time.time(); giving_lives = True
for i in range(N):
    LS.TICK[0] = i
    st = K(0xE000); sg = K(0xE061)
    if st == 5 and not given:
        if not NOCHEAT:
            for a in (0xA0D8, 0xA110): call(a)
        given = True
    if TARGETS and st == 5 and K(0xE1C1):
        oset(mem, 0xE204, K(0xE1C2)); oset(mem, 0xE206, K(0xE1C3))
    if DEATHS and st == 5:
        lv = K(0xE060)
        if lives_was is not None and lv < lives_was:
            deaths.append((i, sg)); died.add(sg); given = False
            print('tick %d: died in stage %d' % (i, sg), flush=True)
            if giving_lives: oset(mem, 0xE060, lives_was); lv = lives_was
        lives_was = lv
        if sg != last_stage: in_stage = 0
        in_stage += 1
        if GAMEOVER and all(s in died for s in range(1, 9)):
            giving_lives = False; mortal(True)
        else:
            mortal(sg not in died and in_stage > DEATH_AT)
    if sg != last_stage or (stages_seen and stages_seen[-1][2] != st and st in (0, 1, 7)):
        stages_seen.append((i, sg, st)); print('tick %d: state %d stage %d  (%.0fs)' % (i, st, sg, time.time() - t0), flush=True)
    last_stage = sg
    TICKS[(st, sg)] += 1
    tick()
    if GAMEOVER and not giving_lives and K(0xE000) in (0, 1) and i > 1000:
        print('tick %d: back at the title after game over' % i, flush=True)
        for _ in range(300):
            LS.TICK[0] += 1; tick()
        break
assert bank is mem.bank
pickle.dump(dict(ex={k: zlib.compress(bytes(v)) for k, v in EX.items()}, rd={k: zlib.compress(bytes(v)) for k, v in RD.items()},
                 disp={k: sorted(v) for k, v in DISP.items()}, ticks=dict(TICKS), stages=stages_seen, deaths=deaths),
            open(OUT, 'wb'))
print('done: %d ticks, %.0fs, %d keys' % (i + 1, time.time() - t0, len(EX)), flush=True)
