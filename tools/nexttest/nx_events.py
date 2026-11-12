"""The Next build's graphics at Konami's load events, in ZEsarUX: for
comparing two .NEX files (1.0N against the no-msx build, during the work
that became 1.1).  Boots the .NEX, starts a game (SPACE), and
lets the ship die until game over and the title; at each event's end (a
breakpoint after Konami's call: the stage loads 0:4103 and 0:414E, the Big
Core 0:4A8D, before each life 0:5452, game over 0:54E0, the title 0:5B62,
the ending 0:4B2C and 0:4C31) saves the Next's store of character rows
(colours: bank 4 E800-FFFF; patterns: bank 6 E800-FFFF), the sprite
patterns (bank 7 F800-FFFF), tile_cdirty/tile_pdirty, Konami's state and
stage, and the screen (save-screen).

usage: nx_events.py FILE.nex SYMFILE OUTDIR [SECONDS]
  SYMFILE   the build's nemesis_next.sym
  ZESARUX   the binary (or zesarux on the PATH); PORT: ZRCP's (default 10000)
  INVULN=1  the ship cannot die (no game over); START=N: the stage to start at
Writes OUTDIR/events.txt and OUTDIR/eNNN.bin (the dumps) and eNNN.bmp."""
import os, sys, re, shutil, socket, subprocess, time
NEX, SYM, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
SECS = float(sys.argv[4]) if len(sys.argv) > 4 else 600
os.makedirs(OUT, exist_ok=True)
sym = {}
for l in open(SYM):
    m = re.match(r'([A-Za-z_][A-Za-z0-9_]*): EQU 0x([0-9A-F]+)', l)
    if m: sym[m.group(1)] = int(m.group(2), 16) & 0xFFFF
POINTS = ['m0_4103', 'm0_414E', 'm0_4A8D', 'm0_5452', 'm0_54E0', 'm0_5B62', 'm0_4B2C', 'm0_4C31']
zes = os.environ.get('ZESARUX') or shutil.which('zesarux')
PORT = int(os.environ.get('PORT', '10000'))

def z(k, c=None, quiet=False):
    if c is not None: k.sendall((c + '\n').encode())
    b = b''
    while not (b.endswith(b'command> ') or b.endswith(b'command@cpu-step> ')):
        d = k.recv(1 << 20)
        if not d: break
        b += d
    return b.decode('latin1')

def nums(out):
    v = []
    for line in out.splitlines():
        m = re.match(r'\s*[0-9A-Fa-f]+H?\s+((?:[0-9A-Fa-f]{2} ?)+)', line)
        if m: v += [int(x, 16) for x in m.group(1).split()]
    return v

p = subprocess.Popen([zes, '--noconfigfile', '--vo', 'null', '--ao', 'null', '--machine', 'TBBlue',
                      '--tbblue-fast-boot-mode', '--allowturbotbbluerom', '--enable-remoteprotocol',
                      '--remoteprotocol-port', str(PORT), '--quickexit', '--snap', os.path.abspath(NEX)],
                     cwd=os.path.dirname(os.path.abspath(zes)), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(3)
    for _ in range(100):
        try: k = socket.create_connection(('127.0.0.1', PORT)); break
        except OSError: time.sleep(0.2)
    k.settimeout(600); z(k)
    z(k, 'enter-cpu-step')
    z(k, 'set-memory-zone 0')
    # where bank 2 is in zone 0: find fixed memory's bytes
    z(k, 'set-memory-zone -1'); probe = nums(z(k, 'hexdump %d 16' % 0x9000)); z(k, 'set-memory-zone 0')
    base = None
    for cand in (0, 0x40000, 0x20000):
        if nums(z(k, 'hexdump %d 16' % (cand + 2 * 0x4000 + 0x1000))) == probe: base = cand; break
    assert base is not None, 'bank 2 not found in zone 0'
    addrs = {}
    for i, n in enumerate(POINTS):
        a = sym[n]; addrs[a] = n
        z(k, 'set-breakpoint %d PC=%XH' % (i + 1, a))
    z(k, 'enable-breakpoints')
    log = open(os.path.join(OUT, 'events.txt'), 'w')
    t0 = time.time(); n = 0; keys_off = None
    z(k, 'set-ui-io-ports 1f1f1f1f1f1f1f1e00')         # SPACE: start
    while time.time() - t0 < SECS:
        out = z(k, 'run 2000000')
        if keys_off is None and time.time() - t0 > 2:
            z(k, 'set-ui-io-ports 1f1f1f1f1f1f1f1f00'); keys_off = True
        pc = int(re.search(r'PC=([0-9a-fA-F]{4})', z(k, 'get-registers')).group(1), 16)
        if pc not in addrs: continue
        z(k, 'set-memory-zone -1')
        st, sg = nums(z(k, 'hexdump %d 1' % (0xE000 - 0x3100)))[0], nums(z(k, 'hexdump %d 1' % (0xE061 - 0x3100)))[0]
        bits = nums(z(k, 'hexdump %d 256' % sym['tile_cdirty']))
        z(k, 'set-memory-zone 0')
        f = os.path.join(OUT, 'e%03d' % n)
        parts = [(4 * 0x4000 + 0x2800, 0x1800), (6 * 0x4000 + 0x2800, 0x1800), (7 * 0x4000 + 0x3800, 0x800)]
        data = b''
        for a, ln in parts:
            z(k, 'save-binary %s.part %d %d' % (f, base + a, ln))
            data += open(f + '.part', 'rb').read(); os.remove(f + '.part')
        open(f + '.bin', 'wb').write(data + bytes(bits))
        z(k, 'save-screen %s.bmp' % f)
        line = '%03d %s state %d stage %d  (%.0fs)' % (n, addrs[pc], st, sg, time.time() - t0)
        print(line, flush=True); log.write(line + '\n'); log.flush()
        n += 1
        if addrs[pc] == 'm0_5B62' and n > 1: break       # the title again: done
        z(k, 'cpu-step')                                   # off the breakpoint
finally:
    p.kill()
