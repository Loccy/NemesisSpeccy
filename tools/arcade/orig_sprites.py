"""Konami's original MSX1 sprite patterns per stage, straight from nem.rom,
by the original loader (0:4249-4287): 86BB to VRAM 1800, then the stage's
two blocks from the table at 0:42B3 (6 bytes a stage, stage 1 first), then
stage 5's extra block 8FCB at 1D00."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys; sys.path.insert(0, (_NEM + '/spec'))
import extract
n = extract.Nemesis((_NEM + '/nem.rom'))
G = extract.GFX
def sprites(stage):
    v = bytearray(0x4000)
    n.decompress(v, n.bank_for(0x86BB, G), 0x86BB, 0x1800)
    t = 0x42AD + 6 * stage
    for k in range(2):
        src = n.u16(0, t + 3 * k); ch = n.u8(0, t + 3 * k + 2)
        n.decompress(v, n.bank_for(src, G), src, 0x1800 + ch * 8)
    if stage == 5:
        n.decompress(v, n.bank_for(0x8FCB, G), 0x8FCB, 0x1D00)
    return bytes(v[0x1800:0x2000])
if __name__ == '__main__':
    s1 = sprites(1)
    for p in (34, 35, 39):
        b = s1[p*32:p*32+32]; print('original stage 1 p%d' % p)
        for r in range(16):
            x = (b[r] << 8) | b[16 + r]; print('  ' + ''.join('#' if x & (0x8000 >> c) else '.' for c in range(16)))
