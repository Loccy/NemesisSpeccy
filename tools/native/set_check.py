"""Check tilemodel.convert against 1.0 itself: the 1.0 test build (every tick
drawn) runs with the MSX original, the same input to both, and at the end of
every tick each tile 1.0 has converted since the last tick (clean in
tile_cdirty / tile_pdirty, attribute bit 7 clear) is compared with the model's
conversion of the MSX's character, in the context 1.0 converted it in (the
state, stage and distance after the previous tick).

Left out: the star characters F6 and F7 (their rows change every tick through
recolour_tile; the native build draws stars itself), and ticks with the
dissolve under way (dz_on; its own path, replaced natively).

usage: [HYPER=1] [TARGETS=1] [DEATHS=1] set_check.py TICKS [SNA]
  SNA: a test build made with NEM_PIN_R=1 NEM_EXTRA=0 (default: this tree's)
"""
import os, sys, time, collections
NEM = os.environ.get('NEM_ROOT') or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
sys.path.insert(0, NEM + '/spec'); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_argv = sys.argv; sys.argv = ['x']
import screen_lockstep as SL
import lockstep_spec as LS
sys.argv = _argv
from layoutsim import explain
from tilemodel import convert

N = int(sys.argv[1]); SNA = sys.argv[2] if len(sys.argv) > 2 else NEM + '/spec/nemesis_test.sna'
HYPER = os.environ.get('HYPER'); TARGETS = os.environ.get('TARGETS'); DEATHS = os.environ.get('DEATHS')
DEATH_AT = int(os.environ.get('DEATH_AT', '900'))

orig = LS.Orig(); LS.patch_front_end(orig); orig.boot()
b = SL.Build(SNA, '1.0')
S = b.syms; B = b.m.mem.banks
CD = S['tile_cdirty'] - 0x8000; PD = S['tile_pdirty'] - 0x8000; DZ = S['dz_on'] - 0x8000
TS = 0xDB00 - 0xC000
def tile(t, ch):
    return [B[7][TS + (9 * t + r) * 256 + ch] for r in range(9)]
last = [None] * 768
checked = collections.Counter(); wrong = collections.defaultdict(list); nwrong = 0
ctx = (0, 0, 0); stage_tick = -99; hyper_done = False; lives_was = None; died = set(); in_stage = 0; last_stage = None
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
            died.add(sg); orig.mem[0xE060] = lives_was; b.setk(0xE060, lives_was); lv = lives_was; hyper_done = False
        lives_was = lv
        if sg != last_stage: in_stage = 0
        in_stage += 1
        on = sg not in died and in_stage > DEATH_AT
        orig.mem.rom[1 * 8192 + 0x75F0 - 0x6000] = 0x00 if on else 0xC9; b.mortal(on)
    if sg != last_stage:
        stage_tick = i; print('tick %d: stage %d (%.0fs)' % (i, sg, time.time() - t0), flush=True)
    last_stage = sg
    LS.sync_tick(orig); b.step(i)
    se, oe = b.k(0xE012), orig.mem[0xE012]
    if se == 0xA6 and oe != 0xA6: LS.msx_sound(orig, 0xA6)
    elif oe == 0xA6 and se != 0xA6: LS.msx_sound(orig, 0xCD)
    a = orig.snapshot()
    bad = [k for k in explain(a, b.ram(), b.mp) if k not in LS.STACK and k not in LS.SOUND]
    if bad: raise SystemExit('tick %d: RAM differs from the MSX' % i)
    vr = orig.vdp.vram
    if not B[2][DZ]:
        for k in range(768):
            t, ch = divmod(k, 256)
            if ch in (0xF6, 0xF7): continue
            o = t * 32 + (ch >> 3); bit = 1 << (ch & 7)
            if (B[2][CD + o] | B[2][PD + o]) & bit: last[k] = None; continue
            got = tile(t, ch)
            if got[8] & 0x80: last[k] = None; continue
            if got == last[k]: continue
            last[k] = got
            pat = [vr[0x2000 + t * 0x800 + ch * 8 + r] for r in range(8)]
            col = [vr[t * 0x800 + ch * 8 + r] for r in range(8)]
            rows, attr = convert(pat, col, t, ch, *ctx)
            key = (ctx[0], ctx[1])
            checked[key] += 1
            if rows != got[:8] or attr != got[8]:
                nwrong += 1
                cat = 'stage change' if i - stage_tick <= 3 else 'mismatch'
                w = wrong[(cat,) + key]
                if len(w) < 6: w.append((i, t, ch, bytes(got).hex(), bytes(rows + [attr]).hex(), bytes(pat).hex(), bytes(col).hex(), ctx[2]))
    else:
        last = [None] * 768
    ctx = (a[0], a[0x61], a[0x63] | a[0x64] << 8)
    if i % 2000 == 0: print('  tick %d  checked %d  wrong %d  (%.0fs)' % (i, sum(checked.values()), nwrong, time.time() - t0), flush=True)
print('checked %d conversions, %d differ from the model' % (sum(checked.values()), nwrong))
print('by (state, stage):', dict(sorted(checked.items())))
for k, v in sorted(wrong.items()):
    print(k, len(v), 'examples (tick, third, char, 1.0, model, pat, col, dist):')
    for e in v: print('   ', e)
