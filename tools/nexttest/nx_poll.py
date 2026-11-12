"""The Next build's graphics at each screen of a game, in ZEsarUX: for
comparing two .NEX files (1.0N against the no-msx build, during the work
that became 1.1).  Runs the .NEX (normal speed x SPEED), starts a
game with SPACE once the title has shown for 6 seconds, then gives no input, so the ship dies in stage 1 until game
over and the title.  Polls Konami's state and stage (E000, E061); one second
after each change of either (and every 10 seconds of play) saves the Next's
store of character rows (colours, bank 4 E800-FFFF; patterns, bank 6
E800-FFFF), the sprite patterns (bank 7 F800-FFFF), tile_cdirty and
tile_pdirty (256 bytes), the name table (name_shadow, 768 bytes); and in
eNNN.l2 both Layer 2 screens (banks 9-11, 13-15: a byte a pixel).

usage: nx_poll.py FILE.nex SYMFILE OUTDIR [SECONDS]
  ZESARUX the binary; PORT ZRCP's port (10000); SPEED emulator speed % (100)
  FIRE=1   fire tapped in play
  TARGETS=1 the ship put on every hidden target (slow, and not seen to work)
  START=N  a new game starts at stage N (the bonus stages: 9-12)
  INVULN=1 the ship cannot die (nx_smoke.py's copy; SYMFILE's directory must
           hold the build's nemesis_next.lst): every stage and the ending
Dumps are taken on a change of state or stage ("change"), when the colour
copy changes in play ("colours": the Big Core, the dissolve) and every 10
seconds of play ("periodic").
Writes OUTDIR/events.txt and OUTDIR/eNNN.bin, eNNN.l2."""
import os, sys, re, shutil, socket, subprocess, time
NEX, SYM, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
SECS = float(sys.argv[4]) if len(sys.argv) > 4 else 400
os.makedirs(OUT, exist_ok=True)
sym = {}
for l in open(SYM):
    m = re.match(r'([A-Za-z_][A-Za-z0-9_]*): EQU 0x([0-9A-F]+)', l)
    if m: sym[m.group(1)] = int(m.group(2), 16) & 0xFFFF
zes = os.environ.get('ZESARUX') or shutil.which('zesarux')
PORT = int(os.environ.get('PORT', '10000')); SPEED = os.environ.get('SPEED', '100')
FIRE = os.environ.get('FIRE') == '1'
BASE = 0x40000                  # 16K bank 0 in ZEsarUX's zone 0 (TBBlue SRAM)

def z(k, c=None):
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

def invulnerable(nex, lst):
    """A copy of the .NEX in which the ship cannot die (as nx_smoke.py)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(lst)))
    import nx_smoke
    here = os.path.dirname(os.path.abspath(lst))
    out = nx_smoke.invulnerable(os.path.abspath(nex), here)
    assert out, 'the death routine not found'
    return out
if os.environ.get('INVULN') == '1':
    NEX = invulnerable(NEX, SYM)
if os.environ.get('START'):
    # a new game starts at stage START: Konami's 0:5588 loads the first
    # stage (its operand, 1), in fixed memory (the .NEX: 512-byte header,
    # then banks 5 and 2)
    a = sym['m0_5588'] + 1
    o = 512 + (a - 0x4000 if a < 0x8000 else 0x4000 + a - 0x8000)
    d = bytearray(open(NEX, 'rb').read())
    assert d[o] == 1, 'the first stage not found at %04X' % a
    d[o] = int(os.environ['START'])
    NEX = os.path.join(OUT, 'start%s.nex' % os.environ['START']); open(NEX, 'wb').write(d)
p = subprocess.Popen([zes, '--noconfigfile', '--vo', 'null', '--ao', 'null', '--machine', 'TBBlue',
                      '--tbblue-fast-boot-mode', '--allowturbotbbluerom', '--emulatorspeed', SPEED,
                      '--enable-remoteprotocol', '--remoteprotocol-port', str(PORT), '--quickexit',
                      '--snap', os.path.abspath(NEX)],
                     cwd=os.path.dirname(os.path.abspath(zes)), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(3)
    for _ in range(100):
        try: k = socket.create_connection(('127.0.0.1', PORT)); break
        except OSError: time.sleep(0.2)
    k.settimeout(60); z(k)
    if os.environ.get('TARGETS') == '1':
        # as screen_lockstep.py's TARGETS: while a hidden target is up (E1C1),
        # the ship is put on it (E204, E206 from E1C2, E1C3) at each tick's end
        cond = 'PC=%XH and PEEK(%XH)=5 and PEEK(%XH)<>0' % (sym['m0_4054'], 0xE000 - 0x3100, 0xE1C1 - 0x3100)
        for i, (dst, src) in enumerate(((0xE204, 0xE1C2), (0xE206, 0xE1C3)), 1):
            z(k, 'set-breakpoint %d %s' % (i, cond))
            z(k, 'set-breakpointaction %d write %XH PEEK(%XH)' % (i, dst - 0x3100, src - 0x3100))
        z(k, 'enable-breakpoints')
    log = open(os.path.join(OUT, 'events.txt'), 'w')
    t0 = time.time(); n = 0; last = None; since = None; done = False; titles = 0; lastdump = 0
    pressed = None; title_at = None; tap = False
    while time.time() - t0 < SECS:
        time.sleep(0.25)
        if pressed is None and last == (1, 0) and time.time() - since > 6:
            z(k, 'set-ui-io-ports 1f1f1f1f1f1f1f1e00'); pressed = time.time()     # SPACE on the title
        if pressed and time.time() - pressed > 1:
            z(k, 'set-ui-io-ports 1f1f1f1f1f1f1f1f00'); pressed = False
        if FIRE and pressed is False and last and last[0] == 5:      # fire, tapped
            tap = not tap
            z(k, 'set-ui-io-ports 1f1f1f1f1f1f1f%s00' % ('1e' if tap else '1f'))
        z(k, 'set-memory-zone -1')
        st, sg = nums(z(k, 'hexdump %d 2' % (0xE000 - 0x3100)))[0], nums(z(k, 'hexdump %d 1' % (0xE061 - 0x3100)))[0]
        now = time.time()
        z(k, 'set-memory-zone 0')
        crc = z(k, 'get-crc32 %d %d' % (BASE + 4 * 0x4000 + 0x2800, 0x1800)).split()[0]
        z(k, 'set-memory-zone -1')
        if (st, sg) != last:
            last = (st, sg); since = now; dumped = False; kind = 'change'; lastcrc = crc
            continue
        if crc != lastcrc and dumped:       # the colours changed in the same state: a load (the Big Core) or the dissolve
            lastcrc = crc; since = now; dumped = False; kind = 'colours'
            continue
        if (not dumped and now - since > 1.0) or (st == 5 and now - lastdump > 10):
            if dumped: kind = 'periodic'
            bits = nums(z(k, 'hexdump %d 256' % sym['tile_cdirty']))
            names = nums(z(k, 'hexdump %d 768' % sym['name_shadow']))
            z(k, 'set-memory-zone 0')
            f = os.path.join(OUT, 'e%03d' % n); data = b''
            for a, ln in ((4 * 0x4000 + 0x2800, 0x1800), (6 * 0x4000 + 0x2800, 0x1800), (7 * 0x4000 + 0x3800, 0x800)):
                z(k, 'save-binary %s.part %d %d' % (f, BASE + a, ln))
                data += open(f + '.part', 'rb').read(); os.remove(f + '.part')
            open(f + '.bin', 'wb').write(data + bytes(bits) + bytes(names))
            l2 = b''
            for bank in (9, 10, 11, 13, 14, 15):      # Layer 2, both screens
                z(k, 'save-binary %s.part %d %d' % (f, BASE + bank * 0x4000, 0x4000))
                l2 += open(f + '.part', 'rb').read(); os.remove(f + '.part')
            open(f + '.l2', 'wb').write(l2)
            line = '%03d %s state %d stage %d  (%.0fs)' % (n, kind, st, sg, now - t0)
            print(line, flush=True); log.write(line + '\n'); log.flush()
            n += 1; dumped = True; lastdump = now
            if st == 1 and pressed is False and os.environ.get('INVULN') != '1': break        # the title after game over: done
finally:
    p.kill()
