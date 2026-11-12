"""Write characters into the character pool (the Next's artwork).

  put_blocks.py STAGE MODULE.py

MODULE defines BLOCKS, {(third, character): 64 pixel values}, and
optionally PALETTE, {value: (RRRGGGBB, B0)} for values D1-DF: the stage's
scenery palette (Layer 2 entries D1-DF, spec/nxgfx/scenery.bin, 32 bytes a
stage).  Each block is stored once in spec/nxgfx/pool.bin (an identical
block already there is shared) and the stage's map (maps.bin) points the
character of that third at it; other stages and thirds are untouched."""
import os, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
GFX = os.path.normpath(os.path.join(HERE, '..', '..', 'spec', 'nxgfx'))
stage = int(sys.argv[1])
spec = importlib.util.spec_from_file_location('art', sys.argv[2]); art = importlib.util.module_from_spec(spec); spec.loader.exec_module(art)
pool = bytearray(open(os.path.join(GFX, 'pool.bin'), 'rb').read())
maps = bytearray(open(os.path.join(GFX, 'maps.bin'), 'rb').read())
sp = os.path.join(GFX, 'scenery.bin')
scen = bytearray(open(sp, 'rb').read()) if os.path.exists(sp) else bytearray(8 * 32)
index = {bytes(pool[k * 64:k * 64 + 64]): k for k in range(len(pool) // 64 - 1, -1, -1)}
new = 0
for (t, c), b in sorted(art.BLOCKS.items()):
    b = bytes(b); assert len(b) == 64
    for v in b:
        assert v < 0x10 or 0x20 <= v < 0xD0 or 0xD1 <= v <= 0xDF, hex(v)
    k = index.get(b)
    if k is None:
        k = len(pool) // 64; pool += b; index[b] = k; new += 1
    e = (stage - 1) * 0x800 + (t * 256 + c) * 2
    maps[e] = 66 + k // 128; maps[e + 1] = k % 128
for v, (b0, b1) in getattr(art, 'PALETTE', {}).items():
    assert 0xD1 <= v <= 0xDF
    o = (stage - 1) * 32 + (v - 0xD0) * 2; scen[o] = b0; scen[o + 1] = b1
open(os.path.join(GFX, 'pool.bin'), 'wb').write(pool)
open(os.path.join(GFX, 'maps.bin'), 'wb').write(maps)
open(sp, 'wb').write(scen)
print('stage %d: %d characters, %d new blocks (pool %d blocks); scenery palette %d colours'
      % (stage, len(art.BLOCKS), new, len(pool) // 64, len(getattr(art, 'PALETTE', {}))))
