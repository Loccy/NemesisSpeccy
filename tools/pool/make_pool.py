"""One-off (3 November 2026): makes the character pool the committed artwork.

  make_pool.py        (writes spec/nxgfx/)

From the stage files as they were (spec/nxgfx/stageN.bin, holding every
character in two colours, the patch's as read from its ROM, with stage 1's
ground edge in browns) and our drawings of the enemies Konami draws with
characters (nx_art_v1.py: CHARS), it writes:
  pool.bin   the character pool: 8 x 8 blocks of Layer 2 pixels (a byte a
             pixel), each different block once, with our drawings in their
             palettes (palette * 16 + value) where those enemies' characters
             are, exactly as nx_pack_v1.py made it in every build;
  maps.bin   8 x 2K: for each stage, 2 bytes for each character of each third
             (third * 256 + character): the 8K page of its block in the .NEX
             (66 on: bank 33 on, 128 blocks a page) and its number in that
             page; page 0: none;
and cuts the stage files' characters down to those Konami rewrites in play
(F6, F7, F8: the stars and a character whose colours Konami cycles), clearing
the rest and their mask bits.  F8 was cut from the stage files afterwards: it
is the ship's shot (F8-FB, which Konami writes into the map), never rewritten
in play, and its pool block is what is drawn.  Run once; the files are the artwork from then
on (nx_pack.py)."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nx_pack_v1 as v1
KEEP = (0xF6, 0xF7, 0xF8)
rom = open(os.path.join(v1.ROOT, 'nem.rom'), 'rb').read()
data = bytearray()
for s in range(1, 9):
    data += open(os.path.join(v1.GFX, 'stage%d.bin' % s), 'rb').read()
art, tab, report, stage_ents = v1.art_page(rom, bytes(data))
pool, n = v1.char_pool(rom, bytes(data), stage_ents)
maps, blocks = pool[:0x4000], pool[0x4000:0x4000 + n * 64]
open(os.path.join(v1.GFX, 'maps.bin'), 'wb').write(maps)
open(os.path.join(v1.GFX, 'pool.bin'), 'wb').write(blocks)
for s in range(1, 9):
    v = bytearray(data[(s - 1) * 0x4000:s * 0x4000])
    for t in range(3):
        for c in range(256):
            if c in KEEP:
                continue
            for base in (0, 0x2000):
                a = base + t * 0x800 + c * 8
                v[a:a + 8] = bytes(8)
                for i in range(8):
                    v[0x3900 + ((a + i) >> 3)] &= ~(1 << ((a + i) & 7)) & 0xFF
    open(os.path.join(v1.GFX, 'stage%d.bin' % s), 'wb').write(v)
print('pool.bin: %d blocks, maps.bin, stage files cut down to characters %s'
      % (n, ', '.join('%02X' % c for c in KEEP)))
