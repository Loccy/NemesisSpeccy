"""End-to-end check of the build-time sets (spec/native_sets.py) against 1.0.

The 1.0 test build (every tick drawn) runs with the MSX original, the same
input to both.  Alongside, a model of the native build's tile set and sprite
patterns is kept: when the MSX reaches one of Konami's load events, the
event's set (complete) or patch is applied, as the native build will.  At the
end of every tick:
  * every tile 1.0 has converted since the last tick (clean, attribute bit 7
    clear) must equal the model's tile for that character;
  * the model's sprite patterns must equal the MSX's.

Left out, as the native build replaces them: the star characters F6 and F7,
ticks while 1.0's dissolve flag is up (dz_on), and characters Konami's
dissolve has changed since they were last loaded (it can run on in the tick
the ending's graphics load and eat part of them).

usage: [HYPER=1] [TARGETS=1] [DEATHS=1] [GAMEOVER=1] native_check.py TICKS SETS.pkl [SNA]
  GAMEOVER=1 (with DEATHS): once every stage 1-8 has had its death, the
  ship stays mortal: game over and the title.  TITLE=0: the title after a
  game over uses title 0's patch (the native choice), not the stage's.
"""
import os, sys, time, collections, pickle
NEM = os.environ.get('NEM_ROOT') or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, NEM + '/spec'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_argv = sys.argv; sys.argv = ['x']
import screen_lockstep as SL
import lockstep_spec as LS
import msxsim
sys.argv = _argv
from layoutsim import explain

N = int(sys.argv[1]); EV = pickle.load(open(sys.argv[2], 'rb'))
SNA = sys.argv[3] if len(sys.argv) > 3 else NEM + '/spec/nemesis_test.sna'
HYPER = os.environ.get('HYPER'); TARGETS = os.environ.get('TARGETS'); DEATHS = os.environ.get('DEATHS')
GAMEOVER = os.environ.get('GAMEOVER'); TITLE0 = os.environ.get('TITLE') == '0'
DEATH_AT = int(os.environ.get('DEATH_AT', '900'))

orig = LS.Orig(); LS.patch_front_end(orig); orig.boot()
b = SL.Build(SNA, '1.0')
S = b.syms; B = b.m.mem.banks
CD = S['tile_cdirty'] - 0x8000; PD = S['tile_pdirty'] - 0x8000; DZ = S['dz_on'] - 0x8000
TS = 0xDB00 - 0xC000
model = {k: bytes(9) for k in range(768)}          # the boot's cleared video memory, converted: blank
mspr = {i: bytes(32) for i in range(64)}
applied = []
dissolved = set()                                  # characters Konami's dissolve has changed since they were loaded
dz_ctx = []
def apply(key):
    e = EV[key]
    model.update(e['tiles']); mspr.update(e['spr']); applied.append((LS.TICK[0], key))
    dissolved.difference_update(e['tiles'])
    if os.environ.get('EVENTS'): print('tick %d: event %s' % (LS.TICK[0], key), flush=True)
class Watched(bytearray):
    def __setitem__(self, a, v):
        bytearray.__setitem__(self, a, v)
        if dz_ctx and a < 0x3800 and not 0x1800 <= a < 0x2000:
            b_ = a if a < 0x1800 else a - 0x2000
            dissolved.add((b_ >> 11) * 256 + ((b_ >> 3) & 255))
orig.vdp.vram = Watched(orig.vdp.vram)
# the load events, by the address of the call that makes them (MSX)
HOOK = {0x422A: lambda: ('stage', orig.mem[0xE061]),
        0x4A6D: lambda: ('bigcore', orig.mem[0xE061]),
        0x53D4: lambda: ('prestage', orig.mem[0xE061]),
        0x54DD: lambda: ('gameover', orig.mem[0xE061]),
        0x5300: lambda: ('title', 0 if TITLE0 else orig.mem[0xE061]),
        0x4B04: lambda: ('ending',),
        0x4C2E: lambda: ('marcador', orig.mem[0xE061])}
pending = []
def tick():
    regs = orig.sim.registers; ops = orig.sim.opcodes; mem = orig.mem; sim = orig.sim
    started = False
    while True:
        pc = regs[24]
        if pc == 0x4054 and started: return
        if pc == 0x40DF and regs[26] and not started:
            orig.vdp.status |= 0x80; orig.int_pending = True; orig.frames += 1
            sim.accept_interrupt(regs, mem, pc); started = True; continue
        if pc < 0x4000 and pc not in msxsim.STUB_RANGE: raise msxsim.Unknown('%04X' % pc)
        h = HOOK.get(pc)
        if h: apply(h())
        if pc == 0xA6C0 and mem.bank[3] == 3 and not dz_ctx:      # Konami's dissolve, 3:A6C0
            dz_ctx.append((mem[regs[12]] | mem[regs[12] + 1] << 8, regs[12]))
        elif dz_ctx and pc == dz_ctx[-1][0] and regs[12] == dz_ctx[-1][1] + 2:
            dz_ctx.pop()
        ops[mem[pc]](); regs[25] += 1
# the title of the first power-on: before the first tick (the boot runs in it)
last = [None] * 768
checked = collections.Counter(); wrong = collections.defaultdict(list); nwrong = 0; sprbad = 0
hyper_done = False; lives_was = None; died = set(); in_stage = 0; last_stage = None; mortal_all = False
t0 = time.time()
for i in range(N):
    LS.TICK[0] = i
    st = orig.mem[0xE000]; sg = orig.mem[0xE061]
    if HYPER and not hyper_done and st == 5:
        before = bytes(orig.mem.ram[0x2000:0x3100]); vbefore = bytes(orig.vdp.vram)
        for a in (0xA0D8, 0xA110): LS.call_msx(orig, a)
        after = bytes(orig.mem.ram[0x2000:0x3100]); vafter = bytes(orig.vdp.vram)
        b2 = B[2]; ns = S['name_shadow'] - 0x8000; d0 = S['dirty0'] - 0x8000
        for k in range(len(after)):
            if after[k] != before[k] and k + 0xE000 not in LS.STACK_MSX: b2[k + SL.KRAM] = after[k]
        for k in range(0x3800, 0x3B00):
            if vafter[k] != vbefore[k]:
                b2[ns + k - 0x3800] = vafter[k]
                for s in (0, 0x80): b2[d0 + s + ((k - 0x3800) >> 3)] |= 1 << ((k - 0x3800) & 7)
        hyper_done = True
    if TARGETS and st == 5 and orig.mem[0xE1C1]:
        for a, v in ((0xE204, orig.mem[0xE1C2]), (0xE206, orig.mem[0xE1C3])): orig.mem[a] = v; b.setk(a, v)
    if DEATHS and st == 5:
        lv = orig.mem[0xE060]
        if lives_was is not None and lv < lives_was:
            died.add(sg); hyper_done = False
            print('tick %d: died in stage %d' % (i, sg), flush=True)
            if not mortal_all: orig.mem[0xE060] = lives_was; b.setk(0xE060, lives_was); lv = lives_was
        lives_was = lv
        if sg != last_stage: in_stage = 0
        in_stage += 1
        if GAMEOVER and all(s in died for s in range(1, 9)): mortal_all = True
        on = mortal_all or (sg not in died and in_stage > DEATH_AT)
        orig.mem.rom[1 * 8192 + 0x75F0 - 0x6000] = 0x00 if on else 0xC9; b.mortal(on)
    if sg != last_stage: print('tick %d: stage %d (%.0fs)' % (i, sg, time.time() - t0), flush=True)
    last_stage = sg
    tick()

    if os.environ.get('EVENTS') and B[2][DZ] != getattr(sys, '_dz', None):
        sys._dz = B[2][DZ]; print('tick %d: dz_on %d' % (i, sys._dz), flush=True)
    b.step(i)
    se, oe = b.k(0xE012), orig.mem[0xE012]
    if se == 0xA6 and oe != 0xA6: LS.msx_sound(orig, 0xA6)
    elif oe == 0xA6 and se != 0xA6: LS.msx_sound(orig, 0xCD)
    a = orig.snapshot()
    if [k for k in explain(a, b.ram(), b.mp) if k not in LS.STACK and k not in LS.SOUND]:
        raise SystemExit('tick %d: RAM differs from the MSX' % i)
    vr = orig.vdp.vram
    shown = set()                              # the patterns of the sprites on show
    for j in range(32):
        if vr[0x3B00 + 4 * j] == 0xD0: break
        shown.add(vr[0x3B02 + 4 * j] >> 2)
    badp = [j for j in sorted(shown) if bytes(vr[0x1800 + j * 32:0x1820 + j * 32]) != mspr[j]]
    if badp:
        sprbad += 1
        if sprbad <= 5: print('tick %d: shown sprite patterns differ from the model: %s' % (i, badp))
    if B[2][DZ]:
        last = [None] * 768
    else:
        for k in range(768):
            t, ch = divmod(k, 256)
            if ch in (0xF6, 0xF7): continue
            o = t * 32 + (ch >> 3); bit = 1 << (ch & 7)
            if k in dissolved: last[k] = None; continue
            if (B[2][CD + o] | B[2][PD + o]) & bit: last[k] = None; continue
            got = bytes(B[7][TS + (9 * t + r) * 256 + ch] for r in range(9))
            if got[8] & 0x80: last[k] = None; continue
            if got == last[k]: continue
            last[k] = got
            checked[(a[0], a[0x61])] += 1
            if got != model[k]:
                nwrong += 1
                key = (a[0], a[0x61], applied[-1][1] if applied else None)
                w = wrong[key]
                if len(w) < 8:
                    o_ = t * 0x800 + ch * 8
                    w.append((i, t, '%02X' % ch, 'dist %04X' % (a[0x63] | a[0x64] << 8), got.hex(), model[k].hex(), 'msx pat ' + bytes(vr[0x2000 + o_:0x2008 + o_]).hex(), 'col ' + bytes(vr[o_:o_ + 8]).hex()))
    if i % 2000 == 0: print('  tick %d  checked %d  wrong %d  sprite ticks wrong %d  (%.0fs)' % (i, sum(checked.values()), nwrong, sprbad, time.time() - t0), flush=True)
    if GAMEOVER and mortal_all and st in (0, 1) and i > 2000 and orig.mem[0xE000] in (0, 1):
        for _ in range(300): pass
print('checked %d conversions, %d differ from the native sets; sprite patterns wrong at %d ticks' % (sum(checked.values()), nwrong, sprbad))
print('events applied:', len(applied), sorted(set(k for _, k in applied)))
print('by (state, stage):', dict(sorted(checked.items())))
for k, v in sorted(wrong.items(), key=str):
    print('state %s stage %s, last event %s: %d+ (tick, third, char, 1.0, native):' % (k[0], k[1], k[2], len(v)))
    for e in v: print('   ', e)
