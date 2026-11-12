"""hunt.py: fulltest.py with a watch for a wild write (8 November 2026: 1.0N
once crashed at the end of stage 5 in the second loop, Konami's stage number
E061 written 7Eh and nx_low.asm's code at 01B1 overwritten).  Breaks on any
write to 01B1 and on E061 written with more than 12 (ZEsarUX opens its
debug menu and the game stops: seen here as Konami's tick counter E003 not
moving); that stops the run and logs the registers, the stack and the CPU history
(the last 3,000 instructions, repeated LDIR/LDDR once; NOHIST=1: none,
which runs faster), disassembled.

Full test of the Next build in ZEsarUX (TBBlue, headless).

Rewritten on 8 November 2026 from the 5 November original (the Next chat;
its copy was left on armadillo).  Plays the whole game with an invulnerable
copy: fire pressed and released throughout, power-ups through Konami's meter
(E130), and (unless NOTARGET) the ship put on each hidden target in stages
1, 2, 3, 4 and 7, which opens the bonus stages (route
1-2-9-3-10-4-11-5-6-7-12-8).  Logs every stage, boss, target and death; at
each stage change and at the end checks bank 8's code, nx_tur.asm's code and
stage 6's tables in page 55, the read-only data pages (57, 59, 61, 63, 80,
the pool 66-79, and the native build's 84-91 when the .NEX has them) against
the .NEX, and that the pool is on.  Dumps (for nx_ftcmp.py, comparing two
builds): at each stage start, every PERIOD seconds, through each boss and
through the ending, as dNNN_TAG.bin (the store of character rows: colours,
patterns, sprite patterns; tile_cdirty/tile_pdirty; name_shadow) and
dNNN_TAG.l2 (both Layer 2 screens).  Then (LOOPS=2) on through the second
loop, or 30 s of it.

  fulltest.py file.nex OUT PORT
  SPECDIR  the build's spec directory (its nemesis_next.sym, nx_low.sym,
           nx_tur.sym, nx_low.lst; default this tree's)
  ZESARUX  the binary; SPD emulator speed % (400); PERIOD seconds (8)
  NOTARGET, NOPOWER, LOOPS (1), LIMIT seconds (5400), STUCK seconds the
  scroll may stand still before the run is called stuck (60; more for slow runs)
The .NEX is made invulnerable here (nx_smoke.py's patch)."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, time, subprocess, socket, re
K = 0x3100
NEX = os.path.abspath(sys.argv[1]); OUT = os.path.abspath(sys.argv[2]); PORT = int(sys.argv[3])
SPD = os.environ.get('SPD', '400'); PERIOD = float(os.environ.get('PERIOD', '8'))
LOOPS = int(os.environ.get('LOOPS', '1')); LIMIT = float(os.environ.get('LIMIT', '5400'))
STUCK = float(os.environ.get('STUCK', '60'))     # seconds the scroll may stand still (a boss fight)
NOTARGET = bool(os.environ.get('NOTARGET')); NOPOWER = bool(os.environ.get('NOPOWER'))
os.makedirs(OUT, exist_ok=True)
ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))
HERE = os.path.abspath(os.environ.get('SPECDIR', os.path.join(ROOT, 'spec')))
sys.path.insert(0, os.path.join(ROOT, 'spec'))
import nx_smoke
ZES = os.environ.get('ZESARUX', (_SCRATCH + '/zes/src/zesarux'))
sym = {}
for f in ('nx_low.sym', 'nemesis_next.sym'):
    for line in open(os.path.join(HERE, f)):
        m = re.match(r'([A-Za-z_][A-Za-z0-9_]*): EQU 0x([0-9A-F]+)', line)
        if m: sym[m.group(1)] = int(m.group(2), 16) & 0xFFFF
tsym = {}
for line in open(os.path.join(HERE, 'nx_tur.sym')):
    m = re.match(r'([A-Za-z_][A-Za-z0-9_.]*): EQU 0x([0-9A-F]+)', line)
    if m: tsym[m.group(1)] = int(m.group(2), 16) & 0xFFFF
CODE = nx_smoke.code_bytes(HERE)
PLAY = nx_smoke.invulnerable(NEX, HERE)
assert PLAY, 'the death routine not found'
# the .nex: 512-byte header, then the 16K banks present, in the order 5, 2, 0, 1, 3, 4, 6, 7, 8, ...
nex = open(NEX, 'rb').read()
order = [5, 2, 0, 1, 3, 4] + list(range(6, 112))
present = [b for b in order if nex[18 + b]]
def nexpage(p):
    i = present.index(p // 2); o = 512 + i * 0x4000 + (p % 2) * 0x2000
    return nex[o:o + 0x2000]
TUR_END = tsym['tu_d'] - 0x6000
TB = tsym.get('TB', 0x7600) - 0x6000
REGIONS = [(55, 0, TUR_END), (55, TB, 0x2000)] + [(p, 0, 0x2000) for p in (57, 59, 61, 63, 80)] + \
          [(p, 0, 0x2000) for p in range(66, 80)]
if 42 in present and any(nexpage(84)):
    REGIONS += [(p, 0, 0x2000) for p in range(84, 92)]          # the native build's graphics loads
T0 = time.time()
logf = open(os.path.join(OUT, 'log.txt'), 'w')
problems = []
def log(s):
    line = '%6.1f %s' % (time.time() - T0, s); print(line, flush=True); logf.write(line + '\n'); logf.flush()
def problem(s):
    problems.append(s); log('PROBLEM: ' + s)
p = subprocess.Popen([ZES, '--noconfigfile', '--vo', 'null', '--ao', 'null', '--machine', 'TBBlue',
                      '--tbblue-fast-boot-mode', '--allowturbotbbluerom', '--emulatorspeed', SPD,
                      '--enable-remoteprotocol', '--remoteprotocol-port', str(PORT), '--quickexit',
                      '--snap', PLAY], cwd=os.path.dirname(ZES),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
k = None
def conn():
    for _ in range(150):
        try:
            s = socket.create_connection(('127.0.0.1', PORT)); s.settimeout(120); return s
        except OSError: time.sleep(0.2)
    raise SystemExit('no connection')
def zr(cmd=None):
    if cmd is not None: k.sendall((cmd + '\n').encode())
    b = b''
    while not re.search(rb'command(@[a-z-]+)?> $', b):
        c = k.recv(1 << 20)
        if not c: raise SystemExit('ZRCP connection closed (emulator gone?)')
        b += c
    return b.decode('latin1')
def rd(a, n=1):
    out = zr('hexdump %d %d' % (a, n)); vals = []
    for line in out.splitlines():
        m = re.match(r'\s*[0-9A-Fa-f]+H?\s+((?:[0-9A-Fa-f]{2} ?)+)', line)
        if m: vals += [int(x, 16) for x in m.group(1).split()]
    return vals[:n]
def r8(a): return rd(a - K)[0]
def r16(a): v = rd(a - K, 2); return v[0] | v[1] << 8
def w8(a, v): zr('write-memory %d %d' % (a - K, v))
def keys(space=False, m=False):
    r7 = 0x1f & ~(1 if space else 0) & ~(4 if m else 0)
    zr('set-ui-io-ports ' + '1f' * 7 + '%02x' % r7 + '00')
def save(phys, n, f):
    zr('set-memory-zone 0')
    zr('save-binary %s %d %d' % (f, 0x40000 + phys, n))
    zr('set-memory-zone -1')
    d = open(f, 'rb').read(); os.remove(f); return d
def page(pg, a, n):
    return save(pg * 0x2000 + a, n, os.path.join(OUT, 'page.tmp'))
ndump = 0
def dump(tag):
    """The store, the marks, the name table, both Layer 2 screens."""
    global ndump
    ndump += 1; f = os.path.join(OUT, 'd%03d_%s' % (ndump, tag))
    t = f + '.tmp'
    data = save(4 * 0x4000 + 0x2800, 0x1800, t) + save(6 * 0x4000 + 0x2800, 0x1800, t) + save(7 * 0x4000 + 0x3800, 0x800, t)
    bits = bytes(rd(sym['tile_cdirty'], 256)); names = bytes(rd(sym['name_shadow'], 768))
    open(f + '.bin', 'wb').write(data + bits + names)
    open(f + '.l2', 'wb').write(save(9 * 0x4000, 0xC000, t) + save(13 * 0x4000, 0xC000, t))
def paused(out): return out.rstrip().endswith('command@cpu-step>')
def wild():
    log('WILD WRITE: ' + zr('get-registers').strip().splitlines()[0])
    log('  stack: ' + zr('get-stack-backtrace 12').strip().replace('\n', ' '))
    m = re.search(r'\d+', zr('cpu-history get-size')); n = int(m.group()) if m else 0
    pcs = re.findall(r'[0-9A-Fa-f]{4}', zr('cpu-history get-pc 0 %d' % min(n, 400)))
    log('  history (newest first): ' + ' '.join(pcs[:400]))
    with open(os.path.join(OUT, 'history.txt'), 'w') as f:
        for i in range(min(n, 400)):
            f.write(zr('cpu-history get-extended %d' % i).strip() + '\n')
    for pc in pcs[:40]:
        log('    ' + zr('disassemble %d 1' % int(pc, 16)).strip().splitlines()[0])
def state():
    return 'stage %d dist %d E000 %02X E151 %02X E152 %02X E1D0 %02X E1D1 %02X' % (
        r8(0xE061), r16(0xE063), r8(0xE000), r8(0xE151), r8(0xE152), r8(0xE1D0), r8(0xE1D1))
def checks(tag):
    lo = rd(0, max(CODE) + 1)
    bad = sorted(a for a, b in CODE.items() if lo[a] != b)
    if bad: problem('%s: bank 8 code changed at %d bytes, first %04X' % (tag, len(bad), bad[0]))
    for pg, a, b in REGIONS:
        got = page(pg, a, b - a); want = nexpage(pg)[a:b]
        if got != want:
            d = [i for i in range(len(want)) if got[i] != want[i]]
            problem('%s: page %d differs at %d bytes, first %04X (%02X, .nex %02X)'
                    % (tag, pg, len(d), a + d[0], got[d[0]], want[d[0]]))
    pool = rd(sym['lo_pool'])[0]
    log('  checks (%s): done, pool %d, %s' % (tag, pool, state()))
    return pool
def powerups():
    for c in (1, 2, 4, 5, 6, 2, 5):
        w8(0xE130, c); keys(m=True); time.sleep(0.15); keys(); time.sleep(0.15)
    log('  power-ups: E131-E136 = %s' % ' '.join('%02X' % v for v in rd(0xE131 - K, 6)))
try:
    time.sleep(3)
    k = conn(); zr()
    log('nex %s (spec %s), %s, speed %s%%, loops %d' % (NEX, HERE, 'no targets' if NOTARGET else 'targets', SPD, LOOPS))
    checks('at start')
    for c in ('enable-breakpoints', 'set-breakpoint 1 MWA=1B1H', 
              *(() if os.environ.get('NOHIST') else ('enter-cpu-step', 'cpu-history enabled yes', 'cpu-history set-max-size 3000',
              'cpu-history ignrepldxr yes', 'cpu-history started yes', 'exit-cpu-step'))):
        r = zr(c).strip().splitlines()
        log('  %s: %s' % (c, r[0] if r and 'command' not in r[0] else 'ok'))
    time.sleep(6)                                   # the title
    keys(space=True); time.sleep(0.4); keys()
    t = time.time()
    while time.time() - t < 30:
        time.sleep(1)
        if r8(0xE000) >= 2 and r16(0xE063) > 0 and r8(0xE200) not in (0, 0xFF): break
    else:
        problem('not in play after 30 s: ' + state()); dump('notinplay'); raise SystemExit
    log('in play: ' + state())
    dump('s1_start')
    if not NOPOWER: powerups()
    stage = r8(0xE061); seen = [stage]; tstage = time.time(); boss = 0; tgt = 0
    fire = False; last_d = -1; t_still = time.time(); t_per = time.time(); burst = 0; t_burst = 0
    loop = 1; ending = False; nend = 0; t_loop2 = None; deaths = 0; dead = False; last_e3 = -1; still3 = 0
    while True:
        fire = not fire; keys(space=fire); time.sleep(0.05)
        e3 = r8(0xE003)
        if e3 == last_e3:
            still3 += 1
            if still3 >= 6:                 # no tick for a while: a breakpoint's menu has stopped it
                v = r8(0xE061); regs = zr('get-registers').strip().splitlines()[0]
                zr('close-all-menus'); zr('enter-cpu-step')
                wild(); problem('wild write: E061 %02X, 01B1 %02X; %s' % (v, rd(0x1B1)[0], regs)); break
        else:
            still3 = 0
        last_e3 = e3
        s = r8(0xE061); d = r16(0xE063); b = r8(0xE151); e1c = rd(0xE1C0 - K, 4); e200 = r8(0xE200)
        e1d0 = r8(0xE1D0)
        if s != stage:
            log('stage %d ended after %.0f s (distance %d); now stage %d' % (stage, time.time() - tstage, last_d, s))
            if s == 1 and stage == 8:
                loop += 1; log('LOOP %d begins: route so far %s' % (loop, '-'.join(map(str, seen))))
                t_loop2 = time.time()
            stage = s; seen.append(s); tstage = time.time(); boss = 0; tgt = 0; t_still = time.time()
            time.sleep(1.5)
            if not checks('start of stage %d' % s): problem('pool off at stage %d' % s)
            dump('s%d_start' % s); t_per = time.time()
        if d != last_d: last_d = d; t_still = time.time()
        if time.time() - t_per > PERIOD:
            t_per = time.time(); dump('s%d_d%d' % (s, d))
        if b and not boss:
            boss = 1; burst = 4; log('  boss (E151 %02X E152 %02X) at distance %d' % (b, r8(0xE152), d))
        if not b and boss == 1:
            boss = 2; log('  boss gone at distance %d' % d); dump('s%d_bossgone' % s)
        if burst and time.time() - t_burst > 2.0:
            burst -= 1; t_burst = time.time(); dump('s%d_boss' % s)
        if e1c[1] and s in (1, 2, 3, 4, 7) and not NOTARGET and loop == 1:
            if not tgt:
                log('  target type %d at row %02X column %02X, distance %d' % (e1c[1], e1c[2], e1c[3], d)); tgt = 1
            w8(0xE204, e1c[2]); w8(0xE206, e1c[3] + 4)
        if e1c[0] and tgt == 1:
            tgt = 2; log('  screen stopped (E1C0 %d): bonus open' % e1c[0])
        if e200 & 0x80 and not dead:
            dead = True; deaths += 1; problem('ship died (E200 %02X) in stage %d at distance %d' % (e200, s, d))
        if not e200 & 0x80: dead = False
        if not e1d0 and ending and loop > nend: ending = False
        if e1d0 and not ending:
            ending = True; nend += 1
            log('ENDING %d (E1D0 %02X) after stage %d: route %s' % (nend, e1d0, s, '-'.join(map(str, seen))))
            te = time.time(); n = 0
            while time.time() - te < 40:
                e = rd(0xE1D0 - K, 10)
                dump('end%d_%02d_%02X%02X' % (nend, n, e[0], e[1])); n += 1
                if not e[0] and time.time() - te > 5: break
                time.sleep(1.0)
            log('  ending dumps: %d; %s' % (n, state()))
            checks('after ending %d' % nend); t_still = time.time(); t_per = time.time()
        if t_loop2 and nend >= LOOPS and loop == nend + 1 and time.time() - t_loop2 > 30:
            dump('loop%d_s1' % loop); checks('30 s into loop %d' % loop); log('done: %d loop(s) complete' % nend); break
        if time.time() - t_still > STUCK and not r8(0xE1D0):
            problem('stuck: distance %d unchanged %d s; %s' % (d, STUCK, state())); dump('stuck'); checks('stuck'); break
        if time.time() - T0 > LIMIT:
            problem('time limit; ' + state()); dump('limit'); break
    log('route %s; deaths %d; dumps %d' % ('-'.join(map(str, seen)), deaths, ndump))
except SystemExit as e:
    if str(e): problem(str(e))
finally:
    log('PROBLEMS: %d' % len(problems))
    for s in problems: log('  ' + s)
    try: keys()
    except Exception: pass
    p.kill()
    if PLAY != NEX and os.path.exists(PLAY): os.remove(PLAY)
