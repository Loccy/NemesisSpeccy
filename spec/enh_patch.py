"""Apply the MSX2 patch's data changes (colours, map pieces) to a Next .NEX.

enh_patch.py file.nex nemesis.sym patches.txt
patches.txt: lines "BANK ADDR OLD NEW" (MSX bank 0-3 and 11, MSX address,
hex bytes).  Bank 0 is in fixed memory (Spectrum bank 5 at 4000 or 2 at
8000), banks 1-2 page A (Spectrum bank 0), 3 page C (bank 4), 11 page E
(bank 1).  Each address is found through the nearest m<bank>_XXXX symbol at
or below it (the relocated instruction or table); the old byte must be
there.  Bytes in code the native build leaves out (reloc/gen.py LEAVE_OUT:
the font and its colours in Konami's status-line loader) are skipped: the
native graphics have them (native_next.py replays the loads with them in)."""
import sys, re
nex = bytearray(open(sys.argv[1], 'rb').read())
syms = {}
for l in open(sys.argv[2]):
    m = re.match(r'^m(\d+)_([0-9A-F]{4}): EQU 0x([0-9A-F]+)', l, re.I)
    if m: syms[(int(m.group(1)), int(m.group(2), 16))] = int(m.group(3), 16)
order = (5, 2, 0, 1, 3, 4, 6, 7)
page = {1: 0, 2: 0, 3: 4, 11: 1}
def off(bank, addr):
    for back in range(0, 0x200 if bank == 0 else 16):
        k = (bank, addr - back)
        if k in syms:
            v = syms[k] + back
            if bank == 0:
                assert 0x4000 <= v <= 0xBFFF, (bank, hex(addr), hex(v))
                return 512 + order.index(5 if v < 0x8000 else 2) * 16384 + (v & 0x3FFF)
            assert 0xC000 <= v <= 0xFFFF, (bank, hex(addr), hex(v))
            return 512 + order.index(page[bank]) * 16384 + v - 0xC000
    if bank == 11:      # map data: copied verbatim to page E C000
        return 512 + order.index(1) * 16384 + addr - 0x8000
    raise SystemExit('no symbol near %d:%04X' % (bank, addr))
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'reloc'))
os.environ.setdefault('NEM_TARGET', 'spec')
import gen
n = 0; gone = 0
for l in open(sys.argv[3]):
    l = l.split('#')[0].split()
    if not l: continue
    bank, addr, old, new = int(l[0]), int(l[1], 16), int(l[2], 16), int(l[3], 16)
    if bank <= 3 and gen.left_out(bank, addr):
        gone += 1; continue         # in code the native build leaves out: in its graphics instead (native_next.py)
    o = off(bank, addr)
    if nex[o] != old:
        raise SystemExit('%d:%04X is %02X, expected %02X' % (bank, addr, nex[o], old))
    nex[o] = new; n += 1
open(sys.argv[1], 'wb').write(nex)
print('%d bytes patched (%d in the native graphics instead)' % (n, gone))
