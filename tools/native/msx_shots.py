"""The MSX alone along screen_lockstep.py's routes (same input, HYPER,
TARGETS, DEATHS as there), its screen saved as PNG at the ticks given.
usage: [HYPER=1] [TARGETS=1] [DEATHS=1] msx_shots.py OUTDIR TICK...
"""
import os, sys
NEM = os.environ.get('NEM_ROOT') or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))
sys.path.insert(0, NEM + '/reloc'); sys.path.insert(0, NEM + '/msxsim'); sys.path.insert(0, NEM + '/spec')
_argv = sys.argv; sys.argv = ['x']
import lockstep_spec as LS
sys.argv = _argv
import screen
OUT = sys.argv[1]; WANT = sorted(int(t) for t in sys.argv[2:])
HYPER = os.environ.get('HYPER'); TARGETS = os.environ.get('TARGETS'); DEATHS = os.environ.get('DEATHS')
DEATH_AT = int(os.environ.get('DEATH_AT', '900'))
os.makedirs(OUT, exist_ok=True)
orig = LS.Orig(); LS.patch_front_end(orig); orig.boot()
hyper_done = False; lives_was = None; died = set(); in_stage = 0; last_stage = None
for i in range(WANT[-1] + 1):
    LS.TICK[0] = i
    st = orig.mem[0xE000]; sg = orig.mem[0xE061]
    if HYPER and not hyper_done and st == 5:
        for a in (0xA0D8, 0xA110): LS.call_msx(orig, a)
        hyper_done = True
    if TARGETS and st == 5 and orig.mem[0xE1C1]:
        orig.mem[0xE204] = orig.mem[0xE1C2]; orig.mem[0xE206] = orig.mem[0xE1C3]
    if DEATHS and st == 5:
        lv = orig.mem[0xE060]
        if lives_was is not None and lv < lives_was:
            died.add(sg); orig.mem[0xE060] = lives_was; lv = lives_was; hyper_done = False
        lives_was = lv
        if sg != last_stage: in_stage = 0
        in_stage += 1
        on = sg not in died and in_stage > DEATH_AT
        orig.mem.rom[1 * 8192 + 0x75F0 - 0x6000] = 0x00 if on else 0xC9
    last_stage = sg
    LS.sync_tick(orig)
    if i in WANT:
        screen.render(orig.vdp, os.path.join(OUT, 't%d_msx.png' % i), 1)
print('done')
