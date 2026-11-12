"""Census of Konami's graphics on the MSX original (msxsim), for the no-msx
128K build (1.1): the first step of that work.

Records, over a scripted game:
  1. every write to the pattern, colour and sprite pattern tables (and, for
     reference, the name table and sprite attributes), by the loader routine
     it is inside (outermost first), the caller, Konami's state and stage;
  2. for every character and sprite pattern shown, which writes its bytes
     came from (its provenance), by state and stage;
  3. stage 3: the distance at which each character is first shown, per
     provenance (the Moai rule applies below 0x195);
  4. RAM written inside the loaders and then read by other code before being
     written again (scratch the native loaders would leave different).

usage: [TARGETS=1] [DEATHS=1] [GAMEOVER=1] census_gfx.py TICKS OUT.pkl
  TARGETS=1   the ship put on every hidden target (the bonus stages)
  DEATHS=1    the ship dies once in each stage (after DEATH_AT ticks in it),
              the life given back; HYPER again after each death
  GAMEOVER=1  (with DEATHS) once every stage 1-8 has had its death, stop
              giving lives back and leave the ship mortal: game over, title
"""
import os, sys, pickle, collections, time
NEM = os.environ.get('NEM_ROOT') or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, NEM + '/spec'); sys.path.insert(0, NEM + '/msxsim'); sys.path.insert(0, NEM + '/reloc')
sys.argv, _argv = ['x'], sys.argv
import lockstep_spec as LS
import msxsim
sys.argv = _argv
N, OUT = int(sys.argv[1]), sys.argv[2]
TARGETS = os.environ.get('TARGETS'); DEATHS = os.environ.get('DEATHS'); GAMEOVER = os.environ.get('GAMEOVER')
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
ram = mem.ram
def K(a): return ram[a - 0xC000]

# ---- loader tracking --------------------------------------------------------
LOADERS = {0x422A: 'stage_gfx', 0x4A6D: 'bigcore', 0x5851: 'marcador', 0x5874: 'marcador2t',
           0x58BA: 'fuente', 0x49B9: 'descomprime', 0x49B3: 'descomprime_dest', 0x4988: 'descomp_3t',
           0x4960: 'vuelca', 0x4964: 'vuelca_3t', 0x4977: 'llena_3t', 0x4371: 'carga_fichas',
           0x475B: 'twinkle', 0x493D: 'borra_pantalla', 0x5746: 'arranca_maquina'}
BANK3 = {0xA6C0: 'dissolve', 0xA765: 'dissolve_chunk', 0xBDD2: 'anima_3'}
active = []          # [name, ret, sp]
def context():
    if active:
        return (active[0][0], active[0][1])
    return None

# ---- VRAM tagging ------------------------------------------------------------
events = {}; evlist = []
def ev_id(key):
    i = events.get(key)
    if i is None:
        i = events[key] = len(evlist); evlist.append(key)
    return i
tags = [0] * 0x4000
ev_id(('boot', 0, 0, 0, 0))
version = [0] * (768 + 64)       # chars (third*256+ch), then sprite patterns
def region(a):
    if a < 0x1800: return 'col'
    if a < 0x2000: return 'spat'
    if a < 0x3800: return 'pat'
    if a < 0x3B00: return 'name'
    if a < 0x3B80: return 'sattr'
    return 'other'
writes = collections.Counter()
def on_vwrite(a):
    c = context(); st = K(0xE000); sg = K(0xE061)
    if c is None:
        sp = regs[12]
        c = ('none', regs[24], mem[sp] | mem[sp + 1] << 8)
    key = (c[0], c[1], st, sg)
    rg = region(a)
    writes[(rg,) + key] += 1
    if rg in ('col', 'pat', 'spat'):
        tags[a] = ev_id(key)
        if rg == 'spat': version[768 + ((a - 0x1800) >> 5)] += 1
        else:
            b = a if a < 0x1800 else a - 0x2000
            version[(b >> 11) * 256 + ((b >> 3) & 255)] += 1
class VRAM(bytearray):
    def __setitem__(self, a, v):
        bytearray.__setitem__(self, a, v)
        on_vwrite(a)
o.vdp.vram = VRAM(o.vdp.vram)

# ---- scratch RAM -------------------------------------------------------------
cls = type(mem); oset = cls.__setitem__; oget = cls.__getitem__
scratch_by = {}                  # address -> loader that last wrote it
watched = {}                     # address -> (loader, state, stage) while unread
scratch_reads = collections.Counter()
scratch_all = collections.defaultdict(set)   # loader -> addresses it wrote
def st_hook(self, a, v):
    if 0xC000 <= a < 0xF000:
        if active:
            scratch_by[a] = active[0][0]; scratch_all[active[0][0]].add(a)
        elif a in watched:
            del watched[a]
    oset(self, a, v)
def get_watch(self, a):
    if a in watched and not active:
        w = watched.pop(a)
        scratch_reads[(a, regs[24], w[0], w[1], w[2])] += 1
        if not watched: cls.__getitem__ = oget
    return oget(self, a)
cls.__setitem__ = st_hook
def loaders_done():
    if scratch_by:
        st = K(0xE000); sg = K(0xE061)
        for a, n in scratch_by.items(): watched[a] = (n, st, sg)
        scratch_by.clear()
        cls.__getitem__ = get_watch

# ---- the stepping loop (lockstep_spec.sync_tick plus loader tracking) --------
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
        if pc < 0x4000 and pc not in msxsim.STUB_RANGE:
            raise msxsim.Unknown('execution at %04X' % pc)
        if active and pc == active[-1][1] and regs[12] == active[-1][2] + 2:
            active.pop()
            while active and pc == active[-1][1] and regs[12] == active[-1][2] + 2:
                active.pop()
            if not active: loaders_done()
        n = LOADERS.get(pc)
        if n is None and pc in BANK3 and mem.bank[3] == 3: n = BANK3[pc]
        if n is not None:
            sp = regs[12]
            active.append((n, oget(mem, sp) | oget(mem, sp + 1) << 8, sp))
        ops[oget(mem, pc)]()
        regs[25] += 1

# ---- what is shown -----------------------------------------------------------
seen_ver = [-1] * (768 + 64)
shown = collections.defaultdict(set)      # (state, stage, kind, index) -> {provenance}
first_dist3 = {}                           # (index, provenance) -> first distance in stage 3
def prov(k):
    if k < 768:
        th, ch = divmod(k, 256); o_ = th * 0x800 + ch * 8
        return frozenset(evlist[tags[o_ + l]] for l in range(8)) | frozenset(evlist[tags[0x2000 + o_ + l]] for l in range(8))
    i = k - 768
    return frozenset(evlist[tags[0x1800 + i * 32 + l]] for l in range(32))
def look():
    v = o.vdp.vram; st = K(0xE000); sg = K(0xE061)
    ks = set()
    for th in range(3):
        base = 0x3800 + th * 256; off = th * 256
        ks.update(off + c for c in bytes(v[base:base + 256]))
    for j in range(32):
        y = v[0x3B00 + 4 * j]
        if y == 0xD0: break
        ks.add(768 + (v[0x3B02 + 4 * j] >> 2))
    d = K(0xE063) | K(0xE064) << 8
    for k in ks:
        if version[k] != seen_ver[k] or (st, sg) != last_ss[0]:
            p = prov(k)
            shown[(st, sg, 'chr' if k < 768 else 'spr', k if k < 768 else k - 768)].add(p)
            if sg == 3 and st == 5 and k < 768 and (k, p) not in first_dist3:
                first_dist3[(k, p)] = d
            seen_ver[k] = version[k]
    last_ss[0] = (st, sg)
last_ss = [None]

# ---- the run -----------------------------------------------------------------
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
    tick()
    look()
    if GAMEOVER and not giving_lives and K(0xE000) in (0, 1) and i > 1000:
        print('tick %d: back at the title after game over' % i, flush=True)
        for _ in range(300):
            LS.TICK[0] += 1; tick(); look()
        break
pickle.dump(dict(writes=dict(writes), shown={k: list(v) for k, v in shown.items()}, first_dist3=first_dist3,
                 scratch_reads=dict(scratch_reads), scratch_all={k: sorted(v) for k, v in scratch_all.items()}, stages=stages_seen, deaths=deaths, events=evlist),
            open(OUT, 'wb'))
print('done: %d ticks, %.0fs, %d events, %d shown keys, %d scratch reads' % (i + 1, time.time() - t0, len(evlist), len(shown), len(scratch_reads)))
