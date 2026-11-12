"""Check the Next's 1.1.3 sprite changes in ZEsarUX (10 November 2026): the
current build, played as nx_feel.py (invulnerable, all weapons, fire rhythm),
on to MAXF frames of play.
  * Character enemy cache: at each hit (lo_pconv after `call nx_cchk`, Z), the
    slot's 128 bytes and lo_ppal are read, Z is cleared and lo_ppal zeroed so
    the conversion runs as before; at `call nx_cput` the slot and lo_ppal are
    read again and compared.
  * Pattern compare: lo_sprites.diff with lo_spe not 64 (the one-a-picture
    safety net found a pattern changed without spr_new): counted.
usage: cachecheck.py NEX OUT PORT MAXF"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, time, socket, re, subprocess, pickle
sys.path.insert(0, (_NEM + '/spec')); import nx_smoke
HERE = (_NEM + '/spec')
NEX, OUT, PORT, MAXF = os.path.abspath(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
K = 0x3100
sym = {}
for f in ('nx_low.sym', 'nemesis_next.sym'):
    for line in open(os.path.join(HERE, f)):
        m = re.match(r'([A-Za-z_][A-Za-z0-9_.]*): EQU 0x([0-9A-F]+)', line)
        if m: sym[m.group(1)] = int(m.group(2), 16) & 0xFFFF
PLAY = nx_smoke.invulnerable(NEX, HERE)
ZES = (_SCRATCH + '/zes/src/zesarux')
p = subprocess.Popen([ZES, '--noconfigfile', '--vo', 'null', '--ao', 'null', '--machine', 'TBBlue',
                      '--tbblue-fast-boot-mode', '--allowturbotbbluerom', '--emulatorspeed', '400',
                      '--enable-remoteprotocol', '--remoteprotocol-port', str(PORT), '--quickexit',
                      '--snap', PLAY], cwd=os.path.dirname(ZES), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(3)
for _ in range(100):
    try:
        k = socket.create_connection(('127.0.0.1', PORT)); break
    except OSError: time.sleep(0.2)
k.settimeout(120); k.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
def zr(cmd=None):
    if cmd is not None: k.sendall((cmd + '\n').encode())
    b = b''
    while not re.search(rb'command(@[a-z-]+)?> $', b):
        k.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
        c = k.recv(1 << 20)
        if not c: raise SystemExit('ZRCP closed')
        b += c
        k.setsockopt(socket.IPPROTO_TCP, socket.TCP_QUICKACK, 1)
    return b.decode('latin1')
def rd(a, n):
    out = zr('hexdump %d %d' % (a, n)); vals = []
    for line in out.splitlines():
        m = re.match(r'\s*[0-9A-Fa-f]+H?\s+((?:[0-9A-Fa-f]{2} ?)+)', line)
        if m: vals += [int(x, 16) for x in m.group(1).split()]
    return vals[:n]
def w8(a, v): zr('write-memory %d %d' % (a, v))
cur = [None]
def keys(space=False):
    rows = [0x1f] * 8
    if space: rows[7] &= ~1
    s = ''.join('%02x' % r for r in rows) + '00'
    if s != cur[0]: zr('set-ui-io-ports ' + s); cur[0] = s
CHEAT = [(0xE132, 0x01), (0xE134, 0x01), (0xE135, 0x01), (0xE136, 0x02), (0xE200, 0x03), (0xE201, 0x0A),
         (0xE202, 0x01), (0xE20B, 0x02), (0xE20C, 0x00), (0xE20E, 0x02), (0xE20F, 0x02),
         (0xE220, 0x01), (0xE22C, 0x44), (0xE22D, 0x0A), (0xE240, 0x01), (0xE24C, 0x44), (0xE24D, 0x0A)]
OPTPOS = [0xE224, 0xE226] + list(range(0xE230, 0xE240)) + [0xE244, 0xE246] + list(range(0xE250, 0xE260))
time.sleep(1); zr()
zr('enter-cpu-step'); zr('enable-breakpoints')
NXF = sym['nx_frame']; HIT = 0x0FD2; PUT = 0x1039; DIFF = sym['lo_sprites.diff']; IDLE = sym['m0_4054']
CODE = {NXF: bytes.fromhex('013b243e1e'), HIT: bytes.fromhex('2868'), PUT: bytes.fromhex('cdd486')}
zr('set-breakpoint 1 PC=%04Xh' % NXF); zr('set-breakpoint 5 PC=%04Xh' % IDLE)
SLOT0 = 0x2800; CI = sym['lo_ci']; PPAL = 0x3FEF; SPE = sym['lo_spe']
f = -1; play_f = None; T0 = time.time(); cheat = False
hits = 0; ok = 0; bad = []; diffs_full = 0; diffs_roll = []; pend = None; st = 0; misses = 0
while True:
    o = zr('run')
    m = re.search(r'Breakpoint fired: PC=([0-9A-F]+)H', o)
    if not m: raise SystemExit('no breakpoint: ' + o[:200])
    pc = int(m.group(1), 16)
    if pc in CODE and bytes(rd(pc, len(CODE[pc]))) != CODE[pc]: continue
    if pc == IDLE:
        if not cheat and rd(0xE000 - K, 1)[0] == 5:
            sy, sx = rd(0xE204 - K, 1)[0], rd(0xE206 - K, 1)[0]
            for a, v in CHEAT: w8(a - K, v)
            for i, a in enumerate(OPTPOS): w8(a - K, sy if i % 2 == 0 else sx)
            cheat = True; zr('disable-breakpoint 5')
        continue
    if pc == NXF:
        f += 1
        r = rd(0xE000 - K, 0x62); e000, st = r[0], r[0x61]
        if e000 == 5 and play_f is None:
            play_f = f; print('play at', f, flush=True)
            zr('set-breakpoint 2 PC=%04Xh' % HIT); zr('set-breakpoint 3 PC=%04Xh' % PUT); zr('set-breakpoint 4 PC=%04Xh' % DIFF)
        keys(space=(f // 25) % 4 == 0)
        if play_f is not None and f - play_f >= MAXF: break
        if f % 1000 == 0:
            print('frame %d stage %d hits %d same %d bad %d misses %d diffs full %d net %d wall %.0f' % (f, st, hits, ok, len(bad), misses, diffs_full, len(diffs_roll), time.time() - T0), flush=True)
            pickle.dump(dict(hits=hits, ok=ok, bad=bad, diffs_roll=diffs_roll, diffs_full=diffs_full), open(OUT, 'wb'))
        continue
    if pc == HIT:
        regs = zr('get-registers'); mm = re.search(r'AF=([0-9A-F]{4})', regs); af = int(mm.group(1), 16)
        if af & 0x40:
            ci = rd(CI, 1)[0] - 1; slot = SLOT0 + ci * 128
            pend = (ci, rd(slot, 128), rd(PPAL, 1)[0], f, st)
            zr('set-register F=%02XH' % ((af & 0xFF) & ~0x40)); w8(PPAL, 0); hits += 1
        else:
            misses += 1; pend = None
        continue
    if pc == PUT:
        if pend:
            ci, before, pal, ff, sst = pend; slot = SLOT0 + ci * 128
            after = rd(slot, 128); pal2 = rd(PPAL, 1)[0]
            if after == before and pal == pal2: ok += 1
            else:
                bad.append((ff, sst, ci, before, after, pal, pal2))
                if len(bad) <= 5: print('MISMATCH frame', ff, 'stage', sst, 'slot', ci, 'pal', pal, pal2, flush=True)
            pend = None
        continue
    if pc == DIFF:
        if rd(SPE, 1)[0] == 64: diffs_full += 1
        else:
            diffs_roll.append((f, st)); print('NET found a pattern change at frame', f, 'stage', st, flush=True)
        continue
pickle.dump(dict(hits=hits, ok=ok, bad=bad, diffs_roll=diffs_roll, diffs_full=diffs_full), open(OUT, 'wb'))
print('done frame %d stage %d hits %d same %d bad %d misses %d diffs full %d net %d' % (f, st, hits, ok, len(bad), misses, diffs_full, len(diffs_roll)), flush=True)
p.kill()
