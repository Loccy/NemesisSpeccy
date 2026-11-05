"""Smoke test of the Spectrum Next build in ZEsarUX (release.sh runs it when
ZEsarUX is there): boot the .NEX, press SPACE, let it play, and check that
Konami's game has started and its scroll is moving, and (with --msx2) that
the stage graphics were put in at the stage load and the background is drawn
from the character pool (lo_pool on, few characters marked as written by
Konami since the stage load: tile_cdirty, tile_pdirty), and that the Next's
code bank (bank 8 at 0000) still holds its code as built: every instruction
byte of nx_low.lst bar the operands the code rewrites itself.  It plays a
copy of the .NEX made invulnerable (Konami's la_nave_ha_muerto, 1:75F0, made
a RET; found by the listing's bytes), so that the ship's dying cannot put
the scroll back between its two samples, and at 28 MHz
(--allowturbotbbluerom: without it ZEsarUX holds a .NEX at 14 MHz).

  nx_smoke.py file.nex [--msx2]
ZEsarUX: $ZESARUX (the binary), or zesarux on the PATH.  It runs headless
(--vo null --ao null) for about a minute and is driven through its remote
protocol (ZRCP) on port 10000."""
import os, sys, shutil, socket, subprocess, time, re

def zrcp_connect(port):
    for _ in range(100):
        try:
            k = socket.create_connection(('127.0.0.1', port))
            k.settimeout(30)
            return k
        except OSError:
            time.sleep(0.2)
    sys.exit('nx_smoke: no ZRCP connection')

def zrcp(k, cmd=None):
    if cmd is not None:
        k.sendall((cmd + '\n').encode())
    b = b''
    while not b.endswith(b'command> '):
        c = k.recv(65536)
        if not c:
            break
        b += c
    return b.decode('latin1')

def peek(k, addr, n):
    out = zrcp(k, 'hexdump %d %d' % (addr, n))
    vals = []
    for line in out.splitlines():
        m = re.match(r'\s*[0-9A-Fa-f]+H?\s+((?:[0-9A-Fa-f]{2} ?)+)', line)
        if m:
            vals += [int(x, 16) for x in m.group(1).split()]
    return vals[:n]

def code_bytes(here):
    """{address: byte} of nx_low.lst's instructions (not the labelled data
    lines), less the operands written by ld (label+n),a."""
    rx = re.compile(r'^\s*\d+\+?\s*([0-9A-F]{4})\s+((?:[0-9A-F]{2} )+)\s*(.*)$')
    code = {}
    for line in open(os.path.join(here, 'nx_low.lst')):
        m = rx.match(line.rstrip('\n'))
        if not m:
            continue
        src = m.group(3).split(';')[0]
        if '...' in line[:40]:
            continue                    # a ds (its bytes cut short): data
        if re.match(r'^[A-Za-z_.][A-Za-z0-9_.]*:', src):
            continue                    # a labelled line: data (db, ds) or a label alone
        a = int(m.group(1), 16)
        for i, b in enumerate(m.group(2).split()):
            code[a + i] = int(b, 16)
    sym = {}
    for line in open(os.path.join(here, 'nx_low.sym')):
        m = re.match(r'([A-Za-z_][A-Za-z0-9_.]*): EQU 0x([0-9A-F]+)', line)
        if m:
            sym[m.group(1)] = int(m.group(2), 16)
    for f in ('nx_low.asm', 'nx_l2.asm'):
        top = None
        for line in open(os.path.join(here, f)):
            m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*):', line)
            if m:
                top = m.group(1)
            for t, n in re.findall(r'ld \((\.?[A-Za-z_][A-Za-z0-9_.]*)\+(\d+)\),a', line):
                name = top + t if t.startswith('.') else t
                if name in sym:
                    code.pop(sym[name] + int(n), None)
    return code

def invulnerable(nex, here):
    """A copy of the .NEX in which the ship cannot die (Konami's 1:75F0, the
    ship's death, returns at once), or None if the routine is not found."""
    lines = open(os.path.join(here, 'nemesis_next.lst')).read().splitlines()
    addr = want = None
    for i, line in enumerate(lines):
        if line.rstrip().endswith('m1_75F0:'):
            addr = int(line.split('+')[1].split()[0], 16)
            want = []
            for l2 in lines[i + 1:i + 12]:           # its first bytes, as listed
                m = re.match(r'\s*\d+\+?\s*([0-9A-F]{4})\s+((?:[0-9A-F]{2} )+)', l2)
                if m: want += [int(x, 16) for x in m.group(2).split()]
            want = want[:6]
            break
    if addr is None or addr < 0xC000 or len(want) < 4:
        return None
    data = bytearray(open(nex, 'rb').read())
    # the .NEX: a 512-byte header, then 16K banks 5, 2, 0, 1, 3, 4, 6, 7, ...
    hits = [512 + i * 0x4000 + addr - 0xC000 for i in range(8)
            if list(data[512 + i * 0x4000 + addr - 0xC000:][:len(want)]) == want]
    if len(hits) != 1:
        return None
    data[hits[0]] = 0xC9
    out = nex[:-4] + '_smoke_invulnerable.nex'
    open(out, 'wb').write(data)
    return out

def main():
    nex = os.path.abspath(sys.argv[1]); msx2 = '--msx2' in sys.argv
    zes = os.environ.get('ZESARUX') or shutil.which('zesarux')
    if not zes:
        print('nx_smoke: ZEsarUX not found (set ZESARUX): skipped'); return 0
    here = os.path.dirname(os.path.abspath(__file__))
    sym = {}
    for f in ('nx_low.sym', 'nemesis_next.sym'):
        for line in open(os.path.join(here, f)):
            m = re.match(r'(lo_enh|lo_pool|tile_cdirty): EQU 0x([0-9A-F]+)', line, re.I)
            if m:
                sym[m.group(1)] = int(m.group(2), 16) & 0xFFFF
    lo_enh = sym.get('lo_enh')
    play = invulnerable(nex, here)
    if play is None:
        print('nx_smoke: the ship\'s death routine (1:75F0) not found: playing the .NEX as it is')
        play = nex
    p = subprocess.Popen([zes, '--noconfigfile', '--vo', 'null', '--ao', 'null',
                          '--machine', 'TBBlue', '--tbblue-fast-boot-mode', '--allowturbotbbluerom',
                          '--enable-remoteprotocol', '--quickexit', '--snap', play],
                         cwd=os.path.dirname(os.path.abspath(zes)),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(3)
        k = zrcp_connect(10000); zrcp(k)
        zrcp(k, 'set-ui-io-ports 1f1f1f1f1f1f1f1e00'); time.sleep(0.4)   # SPACE
        zrcp(k, 'set-ui-io-ports 1f1f1f1f1f1f1f1f00')
        time.sleep(40)
        d1 = peek(k, 0xE063 - 0x3100, 2); time.sleep(10); d2 = peek(k, 0xE063 - 0x3100, 2)
        dist1 = d1[0] | d1[1] << 8; dist2 = d2[0] | d2[1] << 8
        enh = peek(k, lo_enh, 1)[0] if lo_enh is not None else None
        pool = peek(k, sym['lo_pool'], 1)[0] if 'lo_pool' in sym else None
        bits = peek(k, sym['tile_cdirty'], 0x100) if 'tile_cdirty' in sym else None
        nwritten = None if bits is None else sum(bin(b).count('1') for b in bits[:96] + bits[0x80:0x80 + 96])
        code = code_bytes(here)
        lo = peek(k, 0, max(code) + 1)
        bad = sorted(a for a, b in code.items() if lo[a] != b)
    finally:
        p.kill()
        if play != nex:
            os.remove(play)
    ok = dist2 > dist1 > 0
    print('nx_smoke: scroll distance %d -> %d%s' % (dist1, dist2,
          '' if enh is None else ', MSX2 graphics %s' % ('in' if enh else 'not in')))
    if pool is not None:
        print('nx_smoke: character pool %s, %d characters drawn from the copies' %
              ('on' if pool else 'off', nwritten))
    print('nx_smoke: code bank: %d instruction bytes checked, %d changed%s' %
          (len(code), len(bad), '' if not bad else ' (first at %04X)' % bad[0]))
    if bad:
        ok = False
    if msx2 and (not enh or not pool or nwritten > 64):
        ok = False
    print('nx_smoke: %s' % ('ok' if ok else 'FAILED'))
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
