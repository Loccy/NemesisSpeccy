"""Smoke test of the Spectrum Next build in ZEsarUX (release.sh runs it when
ZEsarUX is there): boot the .NEX, press SPACE, let it play, and check that
Konami's game has started and its scroll is moving, and (with --msx2) that
the stage graphics were put in at the stage load and the background is drawn
from the character pool (lo_pool on, few characters marked as written by
Konami since the stage load: tile_cdirty, tile_pdirty), and that the Next's
code bank (bank 8 at 0000) still holds its code as built: every instruction
byte of nx_low.lst bar the operands the code rewrites itself.

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
    p = subprocess.Popen([zes, '--noconfigfile', '--vo', 'null', '--ao', 'null',
                          '--machine', 'TBBlue', '--tbblue-fast-boot-mode',
                          '--enable-remoteprotocol', '--quickexit', '--snap', nex],
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
