"""The Next build in ZEsarUX through the first loop, played as pp_feel.py
plays the 128K and msx_feel.py the MSX: invulnerable, Konami's all-weapons
cheat once play starts (its RAM effect, as the MSX's call leaves it, written
at Konami's idle point 0:4054), keys_default's fire rhythm (SPACE, frames
//25 % 4 == 0), and every 97 frames in play a press of up (Q) or down (A)
towards the middle, held until the screen shows the ship moved.

Stepped frame by frame through ZRCP breakpoints: nx_frame (every frame
interrupt; the flip, if any, has been done in the same interrupt, so
port_bits bit 3 is the screen shown this frame) and lo_render (a screen
about to be drawn into the other buffer: Konami's tick count and the ship's
Y in Konami's sprite list then).  Keys are set at nx_frame, the start of
the frame.  Writes the raw events and a timeline as pp_feel.py does.
usage: nx_feel.py NEX OUT PORT MAX_FRAMES"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, time, socket, re, subprocess, pickle
sys.path.insert(0, (_NEM + '/spec')); import nx_smoke
HERE = os.environ.get('SPECDIR', (_NEM + '/spec'))
NEX, OUT, PORT, MAXF = os.path.abspath(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
K = 0x3100
DELAY = int(os.environ.get('DELAY', '0'))
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
cur_keys = [None]
def keys(space=False, q=False, a=False):
    rows = [0x1f] * 8
    if a: rows[1] &= ~1
    if q: rows[2] &= ~1
    if space: rows[7] &= ~1
    s = ''.join('%02x' % r for r in rows) + '00'
    if s != cur_keys[0]: zr('set-ui-io-ports ' + s); cur_keys[0] = s

# the cheat's RAM effect (MSX addresses), from the simulator (cheatdiff.py):
# E132-E136 the weapons; E200-E25F the ship's state and the two options,
# whose positions (4A, 50 there) are the ship's Y and X then
CHEAT = [(0xE132, 0x01), (0xE134, 0x01), (0xE135, 0x01), (0xE136, 0x02), (0xE200, 0x03), (0xE201, 0x0A),
         (0xE202, 0x01), (0xE20B, 0x02), (0xE20C, 0x00), (0xE20E, 0x02), (0xE20F, 0x02),
         (0xE220, 0x01), (0xE22C, 0x44), (0xE22D, 0x0A), (0xE240, 0x01), (0xE24C, 0x44), (0xE24D, 0x0A)]
OPTPOS = [0xE224, 0xE226] + list(range(0xE230, 0xE240)) + [0xE244, 0xE246] + list(range(0xE250, 0xE260))

time.sleep(1); zr()
zr('enter-cpu-step'); zr('enable-breakpoints')
NXF, LOR, IDLE = sym['nx_frame'], sym['lo_render'], sym['m0_4054']
zr('set-breakpoint 1 PC=%04Xh' % NXF); zr('set-breakpoint 2 PC=%04Xh' % LOR); zr('set-breakpoint 3 PC=%04Xh' % IDLE)
SPR = 0xEC80 - K; PB = sym['port_bits']
frames = []; renders = []; lag = []; press = None; next_press = 0; cheat = False
rendered = {}; f = -1; ticks = 0; last3 = None; start = {}; seen8 = False; T0 = time.time()
def ship_y():
    v = rd(SPR, 128)
    for i in range(32):
        y = v[4 * i]; pt = v[4 * i + 2]
        if y == 0xD0: break
        if pt in (0, 8, 16): return y
    return None
LAG_EVERY = 97
false_hits = 0
while f < MAXF:
    o = zr('run')
    m = re.search(r'Breakpoint fired: PC=([0-9A-F]+)H', o)
    if not m: raise SystemExit('no breakpoint: ' + o[:200])
    pc = int(m.group(1), 16)
    if pc == LOR:
        e003 = rd(0xE003 - K, 1)[0]; pb = rd(PB, 1)[0]
        y = ship_y(); buf = (pb & 8) ^ 8
        renders.append((f, e003, pb, y)); rendered[buf] = (e003, y)
        continue
    if pc == IDLE:
        if not cheat and rd(0xE000 - K, 1)[0] == 5:
            sy, sx = rd(0xE204 - K, 3)[0], rd(0xE206 - K, 1)[0]
            for a, v in CHEAT: w8(a - K, v)
            for i, a in enumerate(OPTPOS): w8(a - K, sy if i % 2 == 0 else sx)
            cheat = True; zr('disable-breakpoint 3')
            print('cheat at frame', f, 'ship', sy, sx, flush=True)
        continue
    # nx_frame: the start of frame f+1 (only if nx_frame's own code is at the
    # PC: page D in; Konami's code in other banks also runs at that address)
    if bytes(rd(NXF, 5)) != b'\x01\x3b\x24\x3e\x1e':
        false_hits += 1
        continue
    f += 1
    ram = rd(0xE000 - K, 0x70); pb = rd(PB, 1)[0]
    e000, e003, st, dist = ram[0], ram[3], ram[0x61], ram[0x63] | ram[0x64] << 8
    if last3 is not None: ticks += (e003 - last3) & 255
    last3 = e003
    shown = rendered.get(pb & 8, (None, None))
    in_play = e000 == 5
    frames.append((f, e000, st, dist, e003, pb, ticks))
    # the press, as pp_feel.py: decided on the screen shown now
    if press is not None and shown[1] is not None and shown[1] != press[1]:
        lag.append(f - press[0] + (64 + (shown[1] + 1) % 256) / 312)
        press = None; next_press = f + LAG_EVERY
    if press is not None and f - press[0] > 50:
        press = None; next_press = f + LAG_EVERY
    if in_play and press is None and f >= next_press and shown[1] is not None:
        y0 = shown[1]; press = (f, y0, 'A' if y0 < 90 else 'Q')
    keys(space=((f + DELAY) // 25) % 4 == 0, q=press is not None and press[2] == 'Q', a=press is not None and press[2] == 'A')
    if in_play:
        if st == 8: seen8 = True
        key = (2 if seen8 and st != 8 else 1, st)
        if key not in start: start[key] = (f, ticks); print('stage', key, 'frame', f, 'wall %.0f s' % (time.time() - T0), flush=True)
        if key[0] == 2: break
    if f % 5000 == 0:
        print('frame', f, 'E000 %02X stage %d dist %d ticks %d lags %d false %d wall %.0f s' % (e000, st, dist, ticks, len(lag), false_hits, time.time() - T0), flush=True)
        pickle.dump(dict(frames=frames, renders=renders, lag=lag, stage_start=start), open(OUT + '.raw.pkl', 'wb'))
pickle.dump(dict(frames=frames, renders=renders, lag=lag, stage_start=start), open(OUT + '.raw.pkl', 'wb'))
print('done', f, len(renders), len(lag), start, 'false nx_frame hits', false_hits, flush=True)
p.kill()
