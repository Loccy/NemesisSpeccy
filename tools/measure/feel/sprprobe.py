"""Next pacing probe (10 November 2026): the current Next build in ZEsarUX,
played as nx_feel.py (invulnerable, fire rhythm, no presses), stage 1.  At
breakpoints, with the frame count (nx_frame hits whose code is nx_frame's) and
ZEsarUX's t-state counter within the frame:
  F  nx_frame: port_bits (the screen shown), frames, flip_due, last_flip, flip_pending
  T  pm_tick: a tick starts (Konami's E003, lo_p30)
  W  pm_wait: the tick is to be drawn (pace_need now)
  R  pm_render: wait_shown has returned
  P  pm_flip: drawn, request_flip next (frames, last_flip, pace_need)
usage: flipprobe.py NEX OUT PORT FRAMES"""
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
def ts():
    o = zr('get-tstates'); m = re.search(r'(-?\d+)', o); return int(m.group(1))
cur = [None]
def keys(space=False):
    rows = [0x1f] * 8
    if space: rows[7] &= ~1
    s = ''.join('%02x' % r for r in rows) + '00'
    if s != cur[0]: zr('set-ui-io-ports ' + s); cur[0] = s
time.sleep(1); zr()
zr('enter-cpu-step'); zr('enable-breakpoints')
BP = dict(F=sym['nx_frame'], S=sym['lo_sprites'], X=0x0D0D, A=sym['lo_sprites.attrs'], O=sym['lo_sprites.cobj'], Q=sym['lo_sprites.rest'], P=sym['pm_flip'])
inv = {v: k2 for k2, v in BP.items()}
zr('set-breakpoint 1 PC=%04Xh' % BP['F'])
NXF_CODE = bytes.fromhex('013b243e1e')
print('nx_frame code', NXF_CODE.hex(), flush=True)
ev = []; f = -1; play_f = None; T0 = time.time()
while True:
    o = zr('run')
    m = re.search(r'Breakpoint fired: PC=([0-9A-F]+)H', o)
    if not m: raise SystemExit('no breakpoint: ' + o[:200])
    kind = inv[int(m.group(1), 16)]
    t = ts()
    if kind == 'F':
        if bytes(rd(BP['F'], 5)) != NXF_CODE: continue
        f += 1
        e000 = rd(0xE000 - K, 1)[0]
        if e000 == 5 and play_f is None:
            play_f = f; print('play at', f, 'wall %.0f' % (time.time() - T0), flush=True)
            for i, k2 in enumerate('SXAOQP'): zr('set-breakpoint %d PC=%04Xh' % (i + 2, BP[k2]))
        if play_f is None:
            keys(space=(f // 25) % 4 == 0); continue
        keys(space=(f // 25) % 4 == 0)
        d3 = rd(sym['flip_due'], 3)
        v = dict(pb=rd(sym['port_bits'], 1)[0], frames=rd(sym['frames'], 1)[0], due=d3[0],
                 last=d3[1], pend=rd(sym['flip_pending'], 1)[0], e000=e000)
        ev.append(('F', f, t, v))
        if play_f is not None and f - play_f >= MAXF: break
        if f % 250 == 0: print('frame', f, 'events', len(ev), 'wall %.0f' % (time.time() - T0), flush=True)
        continue
    if play_f is None: continue
    if kind == 'C':
        dl = rd(sym['lo_dlow'], 1)[0]; bm = rd(sym['dirty0'] + dl, 96)
        v = dict(cells=sum(bin(x).count('1') for x in bm))
    elif kind in 'SXAOQ': v = dict(nobj=rd(sym['lo_nobj'], 1)[0]) if kind == 'X' else {}
    elif kind == 'P': v = dict(need=rd(sym['pace_need'], 1)[0], frames=rd(sym['frames'], 1)[0], last=rd(sym['last_flip'], 1)[0])
    ev.append((kind, f, t, v))
pickle.dump(dict(ev=ev, play_f=play_f), open(OUT, 'wb'))
print('done', f, len(ev), flush=True)
p.kill()
