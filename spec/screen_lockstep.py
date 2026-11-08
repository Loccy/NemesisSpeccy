"""Screen lockstep: two Spectrum test builds (a reference and a candidate)
run side by side with the MSX original, the same input given to all three,
tick by tick.

* Konami's RAM of each Spectrum build is compared with the MSX's, as
  lockstep_spec.py does (addresses explained through each build's own
  symbols), so both builds play exactly the original's game.
* Both Spectrum screens (bank 5 and bank 7: pixels and attributes) of the
  candidate are compared with the reference's at the end of every tick.

Build both as test builds drawing every tick:
    NEM_PIN_R=1 NEM_EXTRA=0 python3 build.py      (writes nemesis_test.sna)

usage: REF=ref.sna [CAND=cand.sna] screen_lockstep.py TICKS
  REF       the reference build's snapshot (its .sym beside it)
  CAND      the candidate's (default: this tree's spec/nemesis_test.sna)
  HYPER=1   every weapon (Konami's own cheat) once play starts
  TARGETS=1 the ship put on every hidden target (the bonus stages)
  DEATHS=1  the ship dies once in each stage, DEATH_AT ticks into it
            (default 900); the life is given back
  ALLOW=f.py  a file defining allow(tick, msx_ram, ref, cand) -> True to
            skip the screen comparison at that tick (intended differences)
  KEEP_GOING=1  count screen differences and go on instead of stopping
  SHOTS=dir     on a screen difference, save both screens and a map of the
            differing cells as PNGs there
"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))
import sys, os, re, time
os.environ.setdefault('NEM_TARGET', 'spec')
sys.path.insert(0, NEM_ROOT + '/reloc'); sys.path.insert(0, NEM_ROOT + '/msxsim'); sys.path.insert(0, NEM_ROOT + '/spec')
_argv = sys.argv; sys.argv = ['x']
import lockstep_spec as LS
sys.argv = _argv
from layoutsim import Mapper, explain
from emu import Spectrum, _syms

KRAM = 0xAF00 - 0x8000
HYPER = os.environ.get('HYPER'); TARGETS = os.environ.get('TARGETS'); DEATHS = os.environ.get('DEATHS')
DEATH_AT = int(os.environ.get('DEATH_AT', '900'))
KEEP = os.environ.get('KEEP_GOING'); SHOTS = os.environ.get('SHOTS')
allow = None
if os.environ.get('ALLOW'):
    _g = {}; exec(open(os.environ['ALLOW']).read(), _g); allow = _g['allow']

class Build:
    def __init__(self, sna, name):
        self.name = name
        self.syms = _syms(sna[:-4] + '.sym')
        self.m = Spectrum(sna)
        self.mp = Mapper(self.syms)
        self.stop = self.syms['m0_4054']
        self.mortal(False)
    def mortal(self, on):
        self.m.mem.banks[0][self.syms['m1_75F0'] - 0xC000] = 0x00 if on else 0xC9
    def k(self, a): return self.m.mem.banks[2][a - 0xE000 + KRAM]
    def setk(self, a, v): self.m.mem.banks[2][a - 0xE000 + KRAM] = v
    def step(self, i):
        m = self.m; regs = m.regs
        row8, joy = LS.keys_for_tick(i, self.k(0xE000) == 5)
        kb = [0] * 8
        if not row8 & 1: kb[7] |= 1
        m.tr.keyboard = kb
        m.sim.trace(m.pc, -1, 1, regs[25] + 70908, 1, None, None, None, None, None)
        m.pc = regs[24]
        m.sim.trace(m.pc, self.stop, 0, regs[25] + 70908 * 1000, 1, None, None, None, None, None)
        m.pc = regs[24]
        if m.pc != self.stop:
            raise SystemExit('tick %d: %s did not reach the tick end (PC %04X)' % (i, self.name, m.pc))
    def ram(self): return bytes(self.m.mem.banks[2][KRAM:KRAM + 0x1100])
    def screens(self): return bytes(self.m.mem.banks[5][:6912]), bytes(self.m.mem.banks[7][:6912])

def cells(a, b):
    """Cells (row, col) whose 8 pixel bytes or attribute differ."""
    out = []
    for r in range(24):
        for c in range(32):
            if a[6144 + r * 32 + c] != b[6144 + r * 32 + c]:
                out.append((r, c)); continue
            for l in range(8):
                o = ((r & 0x18) << 8) | ((r & 7) << 5) | (l << 8) | c
                if a[o] != b[o]:
                    out.append((r, c)); break
    return out

def save(i, s, ra, ca, bad):
    from emu import scr_png
    os.makedirs(SHOTS, exist_ok=True)
    scr_png(ra, os.path.join(SHOTS, 't%d_s%d_ref.png' % (i, s)))
    scr_png(ca, os.path.join(SHOTS, 't%d_s%d_cand.png' % (i, s)))
    m = bytearray(ca); badset = set(bad)
    for r in range(24):
        for c in range(32):
            m[6144 + r * 32 + c] = 0x56 if (r, c) in badset else 0x00 if not (m[6144 + r * 32 + c] & 0x38) and not (m[6144 + r * 32 + c] & 7) else 0x01
    scr_png(bytes(m), os.path.join(SHOTS, 't%d_s%d_map.png' % (i, s)))

def main(N):
    orig = LS.Orig(); LS.patch_front_end(orig); orig.boot()
    ref = Build(os.environ['REF'], 'reference')
    cand = Build(os.environ.get('CAND', os.path.join(NEM_ROOT, 'spec', 'nemesis_test.sna')), 'candidate')
    builds = (ref, cand)
    def setall(a, v):
        orig.mem[a] = v
        for b in builds: b.setk(a, v)
    hyper_done = False; lives_was = None; died = set(); in_stage = 0; last_stage = None
    ndiff = 0; t0 = time.time()
    for i in range(N):
        LS.TICK[0] = i
        st = orig.mem[0xE000]; sg = orig.mem[0xE061]
        if HYPER and not hyper_done and st == 5:
            before = bytes(orig.mem.ram[0x2000:0x3100]); vbefore = bytes(orig.vdp.vram)
            for a in (0xA0D8, 0xA110): LS.call_msx(orig, a)
            after = bytes(orig.mem.ram[0x2000:0x3100]); vafter = bytes(orig.vdp.vram)
            for b in builds:
                b2 = b.m.mem.banks[2]; ns = b.syms['name_shadow'] - 0x8000; d0 = b.syms['dirty0'] - 0x8000
                for k in range(len(after)):
                    if after[k] != before[k] and k + 0xE000 not in LS.STACK_MSX: b2[k + KRAM] = after[k]
                for k in range(0x3800, 0x3B00):
                    if vafter[k] != vbefore[k]:
                        b2[ns + k - 0x3800] = vafter[k]
                        for s in (0, 0x80): b2[d0 + s + ((k - 0x3800) >> 3)] |= 1 << ((k - 0x3800) & 7)
            hyper_done = True
        if TARGETS and st == 5 and orig.mem[0xE1C1]:
            setall(0xE204, orig.mem[0xE1C2]); setall(0xE206, orig.mem[0xE1C3])
        if DEATHS and st == 5:
            lv = orig.mem[0xE060]
            if lives_was is not None and lv < lives_was:
                died.add(sg); setall(0xE060, lives_was); lv = lives_was; hyper_done = False
                print('tick %d: died in stage %d' % (i, sg), flush=True)
            lives_was = lv
            if sg != last_stage: in_stage = 0
            in_stage += 1
            on = sg not in died and in_stage > DEATH_AT
            orig.mem.rom[1 * 8192 + 0x75F0 - 0x6000] = 0x00 if on else 0xC9
            for b in builds: b.mortal(on)
        if sg != last_stage:
            print('tick %d: stage %d  (%.0fs)' % (i, sg, time.time() - t0), flush=True)
        last_stage = sg
        LS.sync_tick(orig)
        for b in builds: b.step(i)
        se, oe = ref.k(0xE012), orig.mem[0xE012]
        if se == 0xA6 and oe != 0xA6: LS.msx_sound(orig, 0xA6)
        elif oe == 0xA6 and se != 0xA6: LS.msx_sound(orig, 0xCD)
        a = orig.snapshot()
        for b in builds:
            bad = [k for k in explain(a, b.ram(), b.mp) if k not in LS.STACK and k not in LS.SOUND]
            if bad:
                print('tick %d: %s: Konami RAM differs from the MSX in %d bytes (state %d): %s' % (
                    i, b.name, len(bad), a[0], ' '.join('%04X' % (0xE000 + k) for k in bad[:20])))
                return 1
        if allow and allow(i, a, ref, cand):
            continue
        for s, (ra, ca) in enumerate(zip(ref.screens(), cand.screens())):
            if ra != ca:
                bad = cells(ra, ca); ndiff += 1
                ns = ref.syms['name_shadow'] - 0x8000; b2 = ref.m.mem.banks[2]
                desc = ', '.join('row %d col %d char %02X attr %02X/%02X' % (r, c, b2[ns + r * 32 + c],
                                 ra[6144 + r * 32 + c], ca[6144 + r * 32 + c]) for r, c in bad[:6])
                print('tick %d: screen %d differs in %d cells (state %d, stage %d, distance %04X): %s' % (
                    i, s, len(bad), a[0], a[0x61], a[0x63] | a[0x64] << 8, desc), flush=True)
                if SHOTS: save(i, s, ra, ca, bad)
                if not KEEP: return 1
        if i % 1000 == 0:
            print('  tick %d ok  state %d  stage %d  (%.0fs)' % (i, a[0], a[0x61], time.time() - t0), flush=True)
    print('all %d ticks: both builds match the MSX%s' % (N, '; screens identical' if not ndiff else '; screen differences at %d ticks' % ndiff))
    return 0 if not ndiff else 1

if __name__ == '__main__':
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 1000))
