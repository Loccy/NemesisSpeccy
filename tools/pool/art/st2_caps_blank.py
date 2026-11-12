"""Stage 2's brick-row end caps, A1 and A4, blank (3 November 2026).  In play
Konami puts them at the ends of the brick rows (Konami's map dumped from the
running game: A1 45 46 ... 45 46 A4, A4 47 48 49 ... 49 A1); on the MSX they
are tips a few pixels wide.  They had been drawn as short slabs, which showed
as cut-off bricks.  They are not wall (characters 77 and above never collide
in stage 2 or the bonus stages, 2:9857), so blank matches what collides."""
BLOCKS = {(t, c): bytes(64) for t in range(3) for c in (0xA1, 0xA4)}
