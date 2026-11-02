"""Smoke test of the Spectrum Next build in ZEsarUX (release.sh runs it when
ZEsarUX is there): boot the .NEX, press SPACE, let it play, and check that
Konami's game has started and its scroll is moving, and (with --msx2) that
the MSX2 graphics were put in at the stage load.

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

def main():
    nex = os.path.abspath(sys.argv[1]); msx2 = '--msx2' in sys.argv
    zes = os.environ.get('ZESARUX') or shutil.which('zesarux')
    if not zes:
        print('nx_smoke: ZEsarUX not found (set ZESARUX): skipped'); return 0
    here = os.path.dirname(os.path.abspath(__file__))
    lo_enh = None
    for line in open(os.path.join(here, 'nx_low.sym')):
        m = re.match(r'lo_enh: EQU 0x([0-9A-F]+)', line, re.I)
        if m:
            lo_enh = int(m.group(1), 16) & 0xFFFF
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
    finally:
        p.kill()
    ok = dist2 > dist1 > 0
    print('nx_smoke: scroll distance %d -> %d%s' % (dist1, dist2,
          '' if enh is None else ', MSX2 graphics %s' % ('in' if enh else 'not in')))
    if msx2 and not enh:
        ok = False
    print('nx_smoke: %s' % ('ok' if ok else 'FAILED'))
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
