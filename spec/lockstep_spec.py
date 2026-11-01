"""Compare the Spectrum build (nemesis_test.sna: randomness pinned) with the
MSX original, tick by tick, on Konami's RAM.

Both sides: ship invulnerable (0x75F0 -> RET), the same R sequence, and the
same keys per tick (SPACE pressed on a fixed rhythm, as in reloc/layoutsim).
Both run the sound driver exactly once before each tick: the test build
calls it from the main loop (not the interrupt), and the MSX side only takes
an interrupt when Konami is idle (its jr $ at 40DF), so every interrupt is
one sound pass plus one tick.  Only the stack area is not compared.

VRAM too: the name table against name_shadow, the colour and pattern tables
against their shadows in pages C and D, the sprite patterns against page 7.

usage: lockstep_spec.py TICKS
"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re, os
os.environ.setdefault('NEM_TARGET', 'spec')   # the relocator's spec layout, for pointers into data (layoutsim.Mapper)
sys.path.insert(0, NEM_ROOT + '/reloc'); sys.path.insert(0, NEM_ROOT + '/msxsim')
sys.path.insert(0, NEM_ROOT + '/spec')
import layoutsim as L
from layoutsim import Original, vclock_tick, Mapper, explain
from emu import Spectrum
from skoolkit.simutils import from_snapshot

HERE = NEM_ROOT + '/spec'
syms = {}
for l in open(os.path.join(HERE, 'nemesis_test.sym')):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF

TICK = [0]

# HOLDFIRE=1: in play, fire held 20 ticks in 40, so the Spectrum's
# hold-to-select (fire_hold: trigger B once fire has been held HOLD_TICKS
# ticks) acts; the MSX is given trigger B by the same rule, as a real second
# button would give it.
HOLDFIRE = os.environ.get('HOLDFIRE')
HOLD_TICKS = int(os.environ.get('NEM_HOLD', '12'))
HELD = {}                       # tick -> ticks fire has been held, this one included

def keys_for_tick(t, started):
    if not started:
        fire = (t % 40) < 4
    elif HOLDFIRE:
        fire = (t % 40) < 20
    else:
        fire = t % 8 < 4
    if t not in HELD:
        HELD[t] = (HELD.get(t - 1, 0) + 1) if fire else 0
    trig_b = HOLDFIRE and fire and HELD[t] - 1 >= HOLD_TICKS
    return (0xFE if fire else 0xFF), (0x1F if trig_b else 0x3F)

class Orig(Original):
    """MSX original, keys from the external tick index."""
    def bios_call(self, pid, r):
        import msxsim
        name = msxsim.NAMES[pid]
        if name in ('SNSMAT', 'RDPSG'):
            row8, joy = keys_for_tick(TICK[0], self.mem[0xE000] == 5)
            if name == 'SNSMAT':
                r[0] = row8 if r[0] == 8 else 0xFF; return
            if r[0] == 14:
                r[0] = joy; return
        L.MSX.bios_call(self, pid, r)

STACK = range(0x1080, 0x10F0)
SOUND = range(0)

STACK_MSX = range(0xF000, 0xF100)

def call_msx(m, addr):
    """Run a routine on the MSX side from Konami's idle loop (4054) and back."""
    regs = m.sim.registers; mem = m.mem; ops = m.sim.opcodes
    sp = (regs[12] - 2) & 0xFFFF
    mem.ram[sp - 0xC000] = 0x54; mem.ram[sp + 1 - 0xC000] = 0x40
    regs[12] = sp; regs[24] = addr
    while regs[24] != 0x4054:
        ops[mem[regs[24]]](); regs[25] += 1

def msx_sound(m, n):
    """Konami's pide_sonido (0:49E9) with sound n, on the MSX side."""
    m.sim.registers[0] = n
    call_msx(m, 0x49E9)

TRACE_AT = int(os.environ.get('TRACE_AT', '0'))
WATCH_AT = int(os.environ.get('WATCH_AT', '0'))          # report every write to WATCH_ADDR (MSX address) in this tick
WATCH_ADDR = int(os.environ.get('WATCH_ADDR', 'E306'), 16)
WATCH_FROM = int(os.environ.get('WATCH_FROM', '0')) or WATCH_AT

def watch_msx(m, a):
    """sync_tick, reporting each instruction that changes MSX byte a."""
    import msxsim
    regs = m.sim.registers; ops = m.sim.opcodes; mem = m.mem; sim = m.sim
    import collections
    started = False; v = mem[a]; hist = collections.deque(maxlen=40)
    while True:
        pc = regs[24]
        if pc == 0x4054 and started:
            return
        if pc == 0x40DF and regs[26] and not started:
            m.vdp.status |= 0x80; m.int_pending = True; m.frames += 1
            sim.accept_interrupt(regs, mem, pc); started = True
            continue
        hist.append((pc, regs[0] if False else None))
        ops[mem[pc]]()
        regs[25] += 1
        if mem[a] != v:
            print('  MSX path: ' + ' '.join('%04X' % h[0] for h in hist))
            v = mem[a]; sp = regs[12]; print('MSX   %04X wrote %02X  (SP %04X: %s)' % (pc, v, sp, ' '.join('%04X' % (mem[sp + 2*j] | mem[sp + 2*j + 1] << 8) for j in range(4))))

def watch_spec(spec, stop, a):
    regs = spec.regs; b = spec.mem.banks[2]; k = a - 0xE000 + 0xAF00 - 0x8000; v = b[k]; n = 0
    while regs[24] != stop and n < 3000000:
        p = regs[24]; pg = spec.tr.out7ffd & 7
        spec.sim.trace(p, -1, 1, regs[25] + 70908, 1, None, None, None, None, None); n += 1
        if b[k] != v:
            v = b[k]; print('Spec  %04X (page %d) wrote %02X' % (p, pg, v))

def trace_crash(spec, stop):
    """Step the Spectrum through one tick keeping the last instructions, and
    print them when it leaves Konami's code for the ROM (or reaches the end)."""
    import collections, bisect
    ks = sorted((v, k) for k, v in syms.items() if '.' not in k); kv = [v for v, k in ks]
    def name(p, pg):
        if p >= 0xC000: return 'page%d+%04X' % (pg, p)
        i = bisect.bisect_right(kv, p) - 1; return '%s+%X' % (ks[i][1], p - ks[i][0])
    regs = spec.regs; hist = collections.deque(maxlen=int(os.environ.get('TRACE_N', '60'))); n = 0
    while regs[24] != stop and n < 3000000:
        p = regs[24]
        if p < 0x4000:
            break
        hist.append((p, spec.tr.out7ffd & 7, regs[12]))
        spec.sim.trace(p, -1, 1, regs[25] + 70908, 1, None, None, None, None, None); n += 1
    last = None
    for p, pg, sp in hist:
        if last is not None and 0x6434 <= p <= 0x6438 and 0x6434 <= last <= 0x6438:
            last = p; continue                 # (the rectangle copy's inner loop)
        last = p
        print('%04X  page %d  SP %04X  %s' % (p, pg, sp, name(p, pg)))
    print('then PC %04X' % regs[24])

def patch_front_end(orig):
    """The Spectrum build's front end (gen.py): no logo, no attract cycle."""
    rom = orig.mem.rom = bytearray(orig.mem.rom)
    rom[0x52D9 - 0x4000:0x52DC - 0x4000] = bytes([0xC3, 0xF3, 0x52])     # jp 52F3
    rom[0x530F - 0x4000:0x5312 - 0x4000] = bytes([0xC3, 0xD3, 0x5B])     # jp 5BD3
    rom[0x584E - 0x4000:0x5850 - 0x4000] = bytes([0x23, 0x00])           # CONTINUE C

def sync_tick(m):
    """MSX: interrupt only at Konami's idle loop; run sound + one tick."""
    import msxsim
    regs = m.sim.registers; ops = m.sim.opcodes; mem = m.mem; sim = m.sim
    started = False
    while True:
        pc = regs[24]
        if pc == 0x4054 and started:
            return
        if pc == 0x40DF and regs[26] and not started:
            m.vdp.status |= 0x80; m.int_pending = True; m.frames += 1
            sim.accept_interrupt(regs, mem, pc); started = True
            continue
        if pc < 0x4000 and pc not in msxsim.STUB_RANGE:
            raise msxsim.Unknown('execution at %04X' % pc)
        ops[mem[pc]]()
        regs[25] += 1

def main(N):
    orig = Orig(); patch_front_end(orig); orig.boot()
    spec = Spectrum(os.path.join(HERE, 'nemesis_test.sna'))
    # invulnerable ship: Konami's la_nave_ha_muerto (MSX 1:75F0) is in page A
    a = syms['m1_75F0']
    spec.mem.banks[0][a - 0xC000] = 0xC9
    stop = syms['m0_4054']
    mp = Mapper(syms)
    sim = spec.sim; regs = spec.regs; tr = spec.tr
    T = spec.t0
    LASER = os.environ.get('LASER')
    HYPER = os.environ.get('HYPER')          # all weapons: the game's own cheat, run on the MSX, its RAM changes copied
    TARGETS = os.environ.get('TARGETS')      # the ship put on every hidden target: the bonus stages
    MORTAL_BONUS = os.environ.get('MORTAL_BONUS')   # (with TARGETS) the ship can die once in each bonus stage
    died = set(); deaths = []; lives_was = None
    hyper_done = False
    b_edges = []; prev_sel = 0
    for i in range(N):
        TICK[0] = i
        if LASER and orig.mem[0xE000] == 5 and orig.mem[0xE20E] == 0:
            for a, v in ((0xE20E, 1), (0xE20C, 0), (0xE20D, 0)):
                orig.mem[a] = v; spec.mem.banks[2][a - 0xE000 + 0xAF00 - 0x8000] = v
        if HOLDFIRE and orig.mem[0xE000] == 5 and HELD.get(i - 1, 0) == HOLD_TICKS and orig.mem[0xE130] == 0:
            v = 1 + (i // 40) % 6                # the bar put on a power-up, both machines, so the press takes it
            orig.mem[0xE130] = v; spec.mem.banks[2][0xE130 - 0xE000 + 0xAF00 - 0x8000] = v
        if HYPER and not hyper_done and orig.mem[0xE000] == 5:
            before = bytes(orig.mem.ram[0x2000:0x3100]); vbefore = bytes(orig.vdp.vram)
            for a in (0xA0D8, 0xA110):                   # HYPER, then a second option
                call_msx(orig, a)
            after = bytes(orig.mem.ram[0x2000:0x3100]); vafter = bytes(orig.vdp.vram)
            for k in range(len(after)):
                if after[k] != before[k] and k + 0xE000 not in STACK_MSX:
                    spec.mem.banks[2][k + 0xAF00 - 0x8000] = after[k]
            ns = syms['name_shadow'] - 0x8000; d0 = syms['dirty0'] - 0x8000
            for k in range(0x4000):
                if vafter[k] != vbefore[k]:
                    if not 0x3800 <= k < 0x3B00:
                        print('HYPER changed VRAM %04X outside the names: not copied' % k); continue
                    spec.mem.banks[2][ns + k - 0x3800] = vafter[k]
                    for s in (0, 0x80):                   # redraw the cell on both screens
                        spec.mem.banks[2][d0 + s + ((k - 0x3800) >> 3)] |= 1 << ((k - 0x3800) & 7)
            hyper_done = True
        if MORTAL_BONUS and orig.mem[0xE000] == 5:
            # the ship can die once in each bonus stage (9-12), on both machines
            # alike; a death is seen as the lives (0xE060) going down, and the
            # life is given back so the run goes on
            st = orig.mem[0xE061]; lv = orig.mem[0xE060]
            if lives_was is not None and lv < lives_was:
                deaths.append((i, st)); print('tick %d: died in stage %d' % (i, st), flush=True)
                died.add(st)
                for a, v in ((0xE060, lives_was),):
                    orig.mem[a] = v; spec.mem.banks[2][a - 0xE000 + 0xAF00 - 0x8000] = v
                lv = lives_was
            lives_was = lv
            mortal = 9 <= st <= 12 and st not in died
            orig.mem.rom[1 * 8192 + 0x75F0 - 0x6000] = 0x00 if mortal else 0xC9
            spec.mem.banks[0][syms['m1_75F0'] - 0xC000] = 0x00 if mortal else 0xC9
        if TARGETS and orig.mem[0xE000] == 5 and orig.mem[0xE1C1]:
            # put the ship on the hidden target, on both machines alike, so
            # each is touched and the bonus stages are played
            for a, v in ((0xE204, orig.mem[0xE1C2]), (0xE206, orig.mem[0xE1C3])):
                orig.mem[a] = v; spec.mem.banks[2][a - 0xE000 + 0xAF00 - 0x8000] = v
        if WATCH_AT and WATCH_FROM <= i <= WATCH_AT:
            print('tick %d: MSX %02X Spec %02X' % (i, orig.mem[WATCH_ADDR], spec.mem.banks[2][WATCH_ADDR - 0xE000 + 0xAF00 - 0x8000]))
            watch_msx(orig, WATCH_ADDR)
        else:
            sync_tick(orig)
        # Spectrum: same keys for this tick (SPACE <-> MSX row 8 bit 0)
        row8, joy = keys_for_tick(i, spec.k(0xE000) == 5)
        kb = [0] * 8
        if not row8 & 1: kb[7] |= 1
        tr.keyboard = kb
        sim.trace(spec.pc, -1, 1, regs[25] + 70908, 1, None, None, None, None, None)   # step off the stop
        spec.pc = regs[24]
        if WATCH_AT and WATCH_FROM <= i <= WATCH_AT:
            watch_spec(spec, stop, WATCH_ADDR)
            if i == WATCH_AT:
                print('watched tick %d' % i); return
        elif TRACE_AT and i == TRACE_AT:
            trace_crash(spec, stop)
            return
        else:
            sim.trace(spec.pc, stop, 0, regs[25] + 70908 * 1000, 1, None, None, None, None, None)
        spec.pc = regs[24]
        if spec.pc != stop:
            print('tick %d: Spectrum did not reach the tick end in 1000 frames (PC %04X)' % (i, spec.pc)); return
        # The title's tune (0.102, title_tick and title_end): the Spectrum plays
        # the attract cycle's tune A6 on the title and stops it (sound CD) when
        # a game starts, where Konami's title is silent; the MSX is given the
        # same request after the same tick (both run the sound driver at the
        # start of a tick, before the title's code requests anything).
        se, oe = spec.k(0xE012), orig.mem[0xE012]
        if se == 0xA6 and oe != 0xA6: msx_sound(orig, 0xA6)
        elif oe == 0xA6 and se != 0xA6: msx_sound(orig, 0xCD)
        a = orig.snapshot()
        b = bytes(spec.mem.banks[2][0xAF00 - 0x8000:0xC000 - 0x8000])
        bad = [k for k in explain(a, b, mp) if k not in STACK and k not in SOUND]
        if bad:
            print('tick %d: %d unexplained bytes (state %d)' % (i, len(bad), a[0]))
            print('  ' + ' '.join('%04X:%02X/%02X' % (0xE000 + k, a[k], b[k]) for k in bad[:40]))
            return
        vr = orig.vdp.vram; B = spec.mem.banks
        regions = (('names', 0x3800, bytes(B[2][syms['name_shadow'] - 0x8000:syms['name_shadow'] - 0x8000 + 768])),
                   ('colours', 0x0000, bytes(B[4][0x2800:0x4000])),
                   ('sprite patterns', 0x1800, bytes(B[7][0x3800:0x4000])),
                   ('patterns', 0x2000, bytes(B[6][0x2800:0x4000])))
        if os.environ.get('SHOT_AT') and i == int(os.environ['SHOT_AT']):
            from emu import scr_png
            scr_png(spec.screen(), os.environ.get('SHOT', 'lockstep_shot.png'))
        if os.environ.get('DUMP_AT') and i == int(os.environ['DUMP_AT']):
            print('MSX  ', vr[0x3800+21*32:0x3800+23*32].hex()); print('Spec ', regions[0][2][21*32:23*32].hex())
        for name, base, got in regions:
            want = vr[base:base + len(got)]
            if want != got:
                d = [k for k in range(len(got)) if want[k] != got[k]]
                print('tick %d: %s differ in %d bytes, e.g. %s' % (i, name, len(d),
                      ' '.join('%04X:%02X/%02X' % (base + k, want[k], got[k]) for k in d[:12])))
                return
        if a[0x08] & 0x20:              # trigger B went down this tick (MSX E008 bit 5)
            b_edges.append((i, prev_sel))
        prev_sel = a[0x130]
        if i % 250 == 0:
            print('  tick %d ok  state %d  phase %d  distance %04X' % (i, a[0], a[0x61], a[0x63] | a[0x64] << 8), flush=True)
    if MORTAL_BONUS: print('deaths (tick, stage):', deaths)
    if HOLDFIRE: print('trigger B presses %d, %d with the bar on a power-up' % (len(b_edges), sum(1 for t, sel in b_edges if sel)))
    print('all %d ticks match (RAM outside the stack and sound records, and VRAM)' % N)

if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 1000)
