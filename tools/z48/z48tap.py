"""Play a 48K tape (spec/nemesis48h.tap, or the test tape nemesis48hc.tap)
in SkoolKit's 48K simulator with scripted keys, loading each stage's block
from the tape as the game asks for it.  Stops at the trap for Konami's code
the 48K leaves out (z48_trap) and prints where it came from.

usage: z48tap.py TAP SECONDS   (SUF=h for nemesis48h.tap's symbols, hc for
                                the test tape's; game seconds, at 50 frames)
Options (environment):
  INV=secs        the ship safe for the first secs of play
  INVST=n         the ship safe while the stage is 1 to n
  GOKEY=C or R    at a game over press C or R after GODELAY frames (150)
  PAUSEAT=f       press H at frame f and again 200 frames later
  SHOTS=prefix    a screenshot every 5 seconds, and at each frame in SHOTAT
  SAVEMEM=f:path  save 4000-FFFF at frame f, and stop
  BORDERLOG=1     every border colour written
  TRAPHIST=f, WATCHPC=label, WATCHM=hex, BRK=label: tracing aids (slow)
Prints Konami's state and stage as they change, the lives, the game overs,
and at the end the frames run, the deaths and the border colour."""
import os, sys, re, pickle
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'spec'))
from emu_bench import scr_png
from skoolkit import ROM48, read_bin_file, CCMIOSimulator
from skoolkit.simutils import from_memory
from skoolkit.trace import Tracer
from fbus import FloatingBusTracer as Tracer

FRAME = 69888
tapf, secs = sys.argv[1], float(sys.argv[2])
SPEC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'spec') + '/'
def syms(n):
    S = {}
    for l in open(SPEC + ('nemesis48' if n == 1 else 'nemesis48_s%d' % n) + os.environ.get('SUF', '') + '.sym'):
        m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
        if m: S[m.group(1)] = int(m.group(2), 16) & 0xFFFF
    return S
d = open(tapf, 'rb').read(); TAPE = []; i = 0
while i < len(d):
    n = d[i] | d[i + 1] << 8; TAPE.append(d[i + 2:i + 2 + n - 1]); i += 2 + n
FF = [b for b in TAPE if b[0] == 0xFF]                        # the BASIC, the loading screen (if any), the first loader
SCR = FF[1][1:] if len(FF) == 3 else None
TAPE = [b for b in TAPE if b[0] not in (0x00, 0xFF)]          # past them (LOAD does those)
tpos = [0]
ldr = open(SPEC + 'tape/loader48.bin', 'rb').read()
LORG = int(re.search(r'org 0x([0-9A-Fa-f]+)', open(SPEC + 'tape/loader48.asm').read()).group(1), 16)
rom = read_bin_file(ROM48)
mem = list(rom) + [0] * 0xC000
if SCR: mem[0x4000:0x5B00] = SCR
mem[LORG:LORG + len(ldr)] = ldr
regs = {'PC': LORG, 'SP': 0xFF00, 'I': 0x3F}
sim = from_memory(CCMIOSimulator, mem, regs, {'im': 1, 'iff': 0, 'tstates': 0}, {'fast_djnz': False, 'fast_ldir': False})
if os.environ.get('BORDERLOG'):                 # every border colour written, and the first frame of each
    sys._bord = {}
    class Tracer(Tracer):
        def write_port(self, registers, port, value, offset=0):
            if port % 2 == 0 and value & 7 not in sys._bord: sys._bord[value & 7] = (registers[25] // FRAME, "%04X" % registers[24])
            return super().write_port(registers, port, value, offset)
tr = Tracer(sim, 0, 0, 0, [None] * 16, 0, False)
sim.set_tracer(tr)
R = sim.registers; M = sim.memory
KRAM = 0xAF00 - 0xE000
k = lambda a: M[a + KRAM]
CUR = [1]; S = syms(1); ORIG = [None]
def ld_bytes():                                  # the ROM's LD-BYTES at 0562, at once
    global S
    flag = R[16]; ix = R[8] << 8 | R[9]; de = R[4] << 8 | R[5]
    if tpos[0] >= len(TAPE):
        print('  tape: at its end, rewound', flush=True); tpos[0] = 0
    blk = TAPE[tpos[0]]; tpos[0] += 1
    if os.environ.get('SHOTS') and blk[0] == flag and flag & 0xF0 == 0x10:   # ldshot: the screen as the load starts
        scr_png(M[0x4000:0x5B00], '%s_ld%d.png' % (os.environ['SHOTS'], R[25] // FRAME))
    ok = blk[0] == flag and len(blk) - 1 == de
    if ok:
        M[ix:ix + de] = blk[1:]
        if flag & 0xF0 in (0x10, 0x20): CUR[0] = flag & 15; S = syms(CUR[0])
        if flag & 0xF0 in (0x10, 0x20):
            mf = SPEC + ('nemesis48' if CUR[0] == 1 else 'nemesis48_s%d' % CUR[0]) + os.environ.get('SUF', '') + '.mem'
            ORIG[0] = open(mf, 'rb').read()[S['m1_75F0'] - 0x4000]      # (from the image: in the core, it is not reloaded)
    print('  tape: block %d flag %02X len %d wanted %02X at %04X len %d: %s (frame %d)' % (tpos[0] - 1, blk[0], len(blk) - 1, flag, ix, de, 'loaded' if ok else 'skipped', R[25] // FRAME), flush=True)
    R[1] = (R[1] | 1) if ok else (R[1] & 0xFE)
    R[25] += 3500000 * (len(blk) // 1500 + 1) // 10   # (a little time)
    sp = R[12]; R[24] = M[sp] | M[sp + 1] << 8; R[12] = sp + 2
COV = os.environ.get('COV'); INV = float(os.environ.get('INV', '0')); SHOTS = os.environ.get('SHOTS')
exe = set() if COV else None

GIVE = os.environ.get('GIVE'); LOW = os.environ.get('LOW')
def call_k(addr):                                # run a Konami routine to its return
    saved = R[:]
    sp = R[12] - 2; M[sp] = 0x05; M[sp + 1] = 0x00
    R[12] = sp; R[24] = addr
    sim.trace(addr, 0x0005, 0, R[25] + FRAME * 50, 1, None, None, None, None, None)
    assert R[24] == 0x0005, 'call %04X did not return' % addr
    for i, v in enumerate(saved):
        if i != 25: R[i] = v
def keys_low(f, st):
    kb = [0] * 8
    if st < 4:
        if (f // 25) % 4 == 0: kb[7] |= 1
        return kb
    if f % 4 < 2: kb[7] |= 1
    ph = (f // 30) % 8
    if ph < 5: kb[1] |= 1                        # mostly down
    elif ph == 6: kb[2] |= 1
    if (f // 100) % 2 == 0: kb[5] |= 1
    else: kb[5] |= 2
    return kb
def keys(f, st):
    if LOW: return keys_low(f, st)
    kb = [0] * 8
    if st < 4:                                   # title: press space now and then
        if (f // 25) % 4 == 0: kb[7] |= 1
        return kb
    if f % 6 < 3: kb[7] |= 1                     # fire (space)
    ph = (f // 40) % 6
    if ph in (0, 1): kb[2] |= 1                  # Q up
    if ph in (3, 4): kb[1] |= 1                  # A down
    if (f // 200) % 3 == 0: kb[5] |= 1           # P right a while
    if (f // 300) % 4 == 1: kb[5] |= 2           # O left a while
    if (f // 500) % 3 == 2: kb[7] |= 4           # M: power-up
    return kb

pc = R[24]; f = 0; play0 = None; last = None; deaths = 0; lives = None; stages = 0
import collections as _c
while f < secs * 50:
    if os.environ.get('TRAPHIST') and f >= int(os.environ['TRAPHIST']):
        if 'hist' not in dir(): hist = _c.deque(maxlen=int(os.environ.get('HLEN', '300')))
        t1 = (f + 1) * FRAME; tp = S['z48_trap']
        while R[25] < t1 and pc != tp and pc != 0x0562 and not (pc < 0x3D00):
            sim.trace(pc, 0, 1, t1, 1, None, None, None, None, None); pc = R[24]; hist.append(pc)
            if os.environ.get('SPH'): sys._sph = getattr(sys, '_sph', _c.deque(maxlen=int(os.environ.get('HLEN', '300')))); sys._sph.append((pc, R[12]))
            if os.environ.get('SPLOW') and R[12] < int(os.environ['SPLOW'], 16): tp = pc; break
            if os.environ.get('WATCHM'):
                wa = int(os.environ['WATCHM'], 16)
                if M[wa] != getattr(sys, '_wm', M[wa]) or not hasattr(sys, '_wm'):
                    if hasattr(sys, '_wm'):
                        inv_s = {}
                        for n_, v_ in S.items(): inv_s.setdefault(v_, n_)
                        ks_ = sorted(inv_s); import bisect as _bb
                        pp = hist[-2] if len(hist) > 1 else 0
                        i_ = _bb.bisect_right(ks_, pp) - 1
                        print('  write %04X: %02X -> %02X by %04X %s f=%d' % (wa, sys._wm, M[wa], pp, inv_s[ks_[i_]], f))
                        if os.environ.get('WHIST'):
                            seen_ = []
                            for p_ in list(hist)[-int(os.environ['WHIST']):]:
                                i2 = _bb.bisect_right(ks_, p_) - 1; n_ = inv_s[ks_[i2]] if i2 >= 0 else '?'
                                if not seen_ or seen_[-1] != n_: seen_.append(n_)
                            print('    path:', ' '.join(seen_[-40:]))
                    sys._wm = M[wa]
            if os.environ.get('WATCHPC') and pc == S.get(os.environ['WATCHPC']) and (os.environ.get('WATCHALL') or not getattr(sys, '_wp', 0)):
                sys._wp = 1
                if os.environ.get('WATCHALL'): print('    ret to %04X' % (M[R[12]] | M[R[12]+1] << 8), end='')
                print('  at %s: A=%02X BC=%02X%02X DE=%02X%02X HL=%02X%02X SP=%04X f=%d' % (os.environ['WATCHPC'], R[0], R[2], R[3], R[4], R[5], R[6], R[7], R[12], f))
        if pc == tp or (pc < 0x3D00 and pc != 0x0562):
            print('  stopped at %04X, frame %d' % (pc, f))
            inv_s = {}
            for n_, v_ in S.items(): inv_s.setdefault(v_, n_)
            ks = sorted(inv_s)
            import bisect as _b
            def nm(a):
                i = _b.bisect_right(ks, a) - 1
                return '%04X %s+%X' % (a, inv_s[ks[i]], a - ks[i]) if i >= 0 else '%04X' % a
            prev = None
            if os.environ.get('HEAD'):
                hl = list(hist); ent = S.get('z48_enter', -1)
                st0 = max((i for i, p in enumerate(hl) if p == ent), default=0)
                hist = hl[st0:st0 + int(os.environ['HEAD'])]
            for p in hist:
                n = nm(p).split('+')[0]
                if n != prev: print('   ', nm(p)); prev = n
            if os.environ.get('SPH'):
                lsp = None
                for p_, s_ in sys._sph:
                    if s_ != lsp: print('    sp %04X at %s' % (s_, nm(p_))); lsp = s_
            print('  stack', ' '.join('%04X' % (M[R[12]+2*i] | M[R[12]+2*i+1] << 8) for i in range(8)))
            if os.environ.get('PEEK'):
                pa = int(os.environ['PEEK'], 16); print('  peek %04X:' % pa, bytes(M[pa:pa + 16]).hex(' '))
            break
        if pc == 0x0562: ld_bytes(); pc = R[24]; continue
        f += 1
        continue
    while True:
        if os.environ.get('BRK') and f >= int(os.environ.get('BRKF', '0')) and os.environ['BRK'] in S:
            bk = S[os.environ['BRK']]
            sim.trace(pc, bk, 0, (f + 1) * FRAME, 1, None, exe, None, None, None)
            pc = R[24]
            if pc == bk:
                print('  brk %s f=%d A=%02X BC=%02X%02X DE=%02X%02X HL=%02X%02X ret %04X' % (os.environ['BRK'], f, R[0], R[2], R[3], R[4], R[5], R[6], R[7], M[R[12]] | M[R[12] + 1] << 8))
                sim.trace(pc, 0, 1, (f + 1) * FRAME, 1, None, None, None, None, None); pc = R[24]
                continue
            break
        sim.trace(pc, 0x0562, 0, (f + 1) * FRAME, 1, None, exe, None, None, None)
        pc = R[24]
        if pc != 0x0562: break
        ld_bytes(); pc = R[24]
    if pc < 0x3D00 and pc != 0x0562:
        print('RESET or ROM (PC %04X) at frame %d, state %d' % (pc, f, k(0xE000))); break
    trap = S['z48_trap']; inv_addr = S['m1_75F0']
    st = k(0xE000)
    if st >= 4 and play0 is None: play0 = f
    inv = play0 is not None and ((f - play0) < INV * 50 or (os.environ.get('INVST') and 1 <= k(0xE061) <= int(os.environ['INVST'])))
    if (INV or os.environ.get('INVST')) and ORIG[0] is not None: M[inv_addr] = 0xC9 if inv else ORIG[0]
    tr.keyboard = keys(f, st)
    if os.environ.get('NOKEYGO') and st == 7: tr.keyboard = [0] * 8     # (game over: no key, so no continue)
    if os.environ.get('GOKEY') and st == 7:      # game over: no key, then R or C after GODELAY frames
        if not getattr(sys, '_go0', None): sys._go0 = f; print('  game over at frame %d (stage %d)' % (f, k(0xE061)), flush=True)
        kb = [0] * 8; d = f - sys._go0
        if d == 100 and SHOTS: scr_png(M[0x4000:0x5B00], '%s_go%d.png' % (SHOTS, f))
        if int(os.environ.get('GODELAY', '150')) <= d < int(os.environ.get('GODELAY', '150')) + 5:
            if os.environ['GOKEY'] == 'R': kb[2] |= 0x08
            else: kb[0] |= 0x08
        tr.keyboard = kb
    elif os.environ.get('GOKEY') and getattr(sys, '_go0', None) and st != 7:
        print('  left game over at frame %d: state %d, stage %d' % (f, st, k(0xE061)), flush=True); sys._go0 = None
    if os.environ.get('PAUSEAT'):
        p0 = int(os.environ['PAUSEAT'])
        if p0 <= f < p0 + 5 or p0 + 200 <= f < p0 + 205:
            kb = list(tr.keyboard); kb[6] |= 0x10; tr.keyboard = kb      # H: the pause
        if f in (p0 + 100, p0 + 300): print('  f=%d paused E10B=%02X E047=%02X pc=%04X' % (f, k(0xE10B), k(0xE047), pc), flush=True)
    if GIVE and st == 5 and not getattr(sys, '_given', False) and play0 is not None and f - play0 > 120:
        sys._given = True
        call_k(S['m3_A0B7']); call_k(S['m3_A0C1']); call_k(S['m3_A0C1']); pc = R[24]
        print('given laser and two options at frame', f)
    if os.environ.get('STEP'):
        snaps = (snaps if f else [])[-2:] + [(R[:], M[:], f)]
        snap = snaps[0]
    else: snap = None
    if False:
        print('RESET (PC 0) at frame %d, state %d' % (f, k(0xE000)))
        if snap:
            R[:] = snap[0]; M[:] = snap[1]; pc = R[24]; hist = []
            for ff in range(snap[2], f + 1):
                tr.keyboard = keys(ff, k(0xE000))
                while pc != 0 and R[25] < (ff + 1) * FRAME:
                    sim.trace(pc, 0, 1, (ff + 1) * FRAME, 1, None, None, None, None, None)
                    hist.append(pc); pc = R[24]
            print('last PCs:', ' '.join('%04X' % x for x in hist[-60:]))
        break
    if trap <= pc < trap + 0x30:
        h = S['z48_trap_hex']
        print('TRAP shown at frame %d: %s' % (f, bytes(M[h:h + 4]).decode()))
        break
    if pc == trap and snap:                      # again, a step at a time, for the last PCs
        R[:] = snap[0]; M[:] = snap[1]; pc = R[24]; hist = []
        for ff in range(snap[2], f + 1):
            tr.keyboard = keys(ff, k(0xE000))
            while pc != trap and R[25] < (ff + 1) * FRAME:
                sim.trace(pc, trap, 1, (ff + 1) * FRAME, 1, None, None, None, None, None)
                hist.append(pc); pc = R[24]
        while False:
            hist.append(pc); pc = R[24]
        j = next((i for i, x in enumerate(hist) if x < 0x1000), len(hist) - 1)
        if any(x < 0x1000 for x in hist[-200:]):
            print('into low memory from:', ' '.join('%04X' % x for x in hist[max(0, j - 30):j + 3]))
        print('last PCs:', ' '.join('%04X' % x for x in hist[-40:]))
    if pc == trap:
        sp = R[12]
        print('TRAP at frame %d: state %d stage %d; stack:' % (f, k(0xE000), k(0xE061)),
              ' '.join('%04X' % (M[sp + 2 * i] | M[sp + 2 * i + 1] << 8) for i in range(12)))
        break
    if os.environ.get('PROBE') and (f % 25 == 0) and (int(os.environ['PROBE']) <= f < int(os.environ['PROBE']) + 400):
        print('  probe f=%d pc=%04X sp=%04X iff=%d E000=%02X E001=%02X E063=%02X%02X E065=%02X E101-106=%s E107=%02X E10F=%02X E140=%02X E148=%02X%02X E150=%02X E151=%02X E1D0=%02X E1D1=%02X E1C0=%02X E200=%02X E012=%02X E00x=%s' % (
            f, pc, R[12], R[26], k(0xE000), k(0xE001), k(0xE064), k(0xE063), k(0xE065), bytes(M[0xE101+KRAM:0xE107+KRAM]).hex(), k(0xE107), k(0xE10F), k(0xE140), k(0xE149), k(0xE148), k(0xE150), k(0xE151), k(0xE1D0), k(0xE1D1), k(0xE1C0), k(0xE200), k(0xE012), bytes(M[0xE000+KRAM:0xE010+KRAM]).hex()), flush=True)
    if os.environ.get('HIST') and f == int(os.environ['HIST']):
        import collections; hc = collections.Counter(); p = pc; t0 = R[25]
        while R[25] < t0 + FRAME:
            sim.trace(p, 0, 1, t0 + FRAME, 1, None, None, None, None, None); p = R[24]; hc[p] += 1
        inv_s = {v: n for n, v in S.items()}
        def nm(a):
            c = [v for v in inv_s if v <= a and a - v < 0x400]
            return '%s+%X' % (inv_s[max(c)], a - max(c)) if c else '?'
        print('  hist:', ', '.join('%04X %s %d' % (a, nm(a), n) for a, n in hc.most_common(25)))
        pc = p
    if f == 400: M[0xBF81:0xBFB6] = [0xE5] * 0x35
    if f == 9900: print('  stack: lowest written by frame 9900: %s' % next(('%04X' % (0xBF81 + i) for i in range(0x35)[::-1] if M[0xBF81 + i] != 0xE5 and all(M[0xBF81 + j] != 0xE5 for j in range(i, 0x35))), 'none below BFB6'))
    if str(f) in os.environ.get('DUMPAT', '').split(','):
        print('  dump f=%d EC80: %s' % (f, bytes(M[0xEC80+KRAM:0xECA8+KRAM]).hex(' ')))
        print('  dump f=%d E200: %s' % (f, bytes(M[0xE200+KRAM:0xE220+KRAM]).hex(' ')))
    if os.environ.get('OBJAT') and f % int(os.environ.get('OBJEVERY','100')) == 0 and int(os.environ['OBJAT']) <= f < int(os.environ['OBJAT']) + int(os.environ.get('OBJLEN','2000')):
        objs = [bytes(M[0xE300 + KRAM + 32 * i:0xE300 + KRAM + 32 * i + 4]).hex() for i in range(12)]
        print('  obj f=%d dist %04X E111=%02X: %s' % (f, k(0xE063) | k(0xE064) << 8, k(0xE111), ' '.join(o for o in objs if o[:2] != '00')), flush=True)
    if os.environ.get('CMPCORE') and f % int(os.environ['CMPCORE']) == 0 and f > 200:
        if not hasattr(sys, '_core'): sys._core = open(SPEC + 'nemesis48' + os.environ.get('SUF', '') + '.mem', 'rb').read()
        dd = [a for a in range(0x5B00, 0xAD00) if M[a] != sys._core[a - 0x4000]]
        dd = [a for a in dd if not getattr(sys, '_okd', None) or a not in sys._okd]
        if dd and not hasattr(sys, '_okd'): sys._okd = set(dd); print('  core: %d bytes changed by frame %d (variables): %s' % (len(dd), f, ' '.join('%04X' % a for a in dd[:12])))
        elif dd: print('  core: new changes by frame %d: %s' % (f, ' '.join('%04X' % a for a in dd[:16]))); sys._okd |= set(dd)
    lv = k(0xE060)
    if lives is not None and lv < lives: deaths += 1
    lives = lv
    cur = (k(0xE000), k(0xE061))
    if cur != last:
        print('f=%5d (%.1fs) state %d stage %d lives %d dist %04X' % (f, f / 50, cur[0], cur[1], lv, k(0xE063) | k(0xE064) << 8), flush=True)
        last = cur
    if os.environ.get('RAMCEN'):
        if f == 0: nz = bytearray(0x1100)
        for i, v in enumerate(M[0xAF00:0xC000]):
            if v: nz[i] = 1
    if os.environ.get('MON') and f % 250 == 0 and st >= 5:
        print('  t=%ds dist %04X boss E151=%02X E152=%02X E190=%02X E153=%02X z48_bc=%d' % (f // 50, k(0xE063) | k(0xE064) << 8,
              k(0xE151), k(0xE152), k(0xE190), k(0xE153), M[S['z48_bc']]), flush=True)
    if SHOTS and (f % 250 == 249 or str(f) in os.environ.get('SHOTAT', '').split(',')):
        scr_png(M[0x4000:0x5B00], '%s_%04d.png' % (SHOTS, f // 50 + 1) if f % 250 == 249 else '%s_f%d.png' % (SHOTS, f))
    if os.environ.get('SAVEMEM') and f == int(os.environ['SAVEMEM'].split(':')[0]):
        open(os.environ['SAVEMEM'].split(':')[1], 'wb').write(bytes(M[0x4000:0x10000])); print('  memory saved at f=%d' % f); break
    if os.environ.get('EXPLO'):
        ty = [k(0xE800 + 8 * i) for i in range(4)]
        if 0x20 in ty and not hasattr(sys, '_ex'):
            sys._ex = f; print('  background explosion at f=%d dist %04X slots %s' % (f, k(0xE063) | k(0xE064) << 8, bytes(M[0xE800+KRAM:0xE820+KRAM]).hex(' ')), flush=True)
        if hasattr(sys, '_ex') and (f - sys._ex) % 3 == 0 and f - sys._ex <= 45:
            scr_png(M[0x4000:0x5B00], '%s_x%d.png' % (os.environ['EXPLO'], f))
            print('  f=%d slots %s' % (f, bytes(M[0xE800+KRAM:0xE820+KRAM]).hex(' ')), flush=True)
        if hasattr(sys, '_ex') and f - sys._ex > 45: break
    f += 1
if os.environ.get('BORDERLOG'): print('border colours written (colour: first frame):', sys._bord)
print('ran %d frames; deaths %d; border %s' % (f, deaths, tr.outfe if hasattr(tr, 'outfe') else '?'))
if os.environ.get('RAMCEN'):
    pickle.dump(bytes(nz), open(os.environ['RAMCEN'], 'wb'))
if COV:
    pickle.dump(exe, open(COV, 'wb'))
    print('executed addresses:', len(exe))
