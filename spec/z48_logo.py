"""The 48K title's logo in block characters (14 November 2026).

The letters of the 128K's title logo, drawn by hand on the grid of the
Spectrum's block characters: each character cell is 2 by 2 blocks of 4 by 4
pixels.  10 rows of 64 blocks: 5 rows of 32 cells, shown at screen rows 2-6
(z48_logo in stage 1's block, called by z48_title through the header's
pointer, OV48+52).

Colours: the letters bright cyan, with a white line above the top bars and
below the feet; character rows 1 and 3 dark cyan (BRIGHT 0), the original's
dithered bands.  A cell holds at most two colours, so the white lines sit
over (row 0) or under (row 4) a full half-cell of cyan: such a cell is white
ink on cyan paper, its ink the white half.

data() gives the 80 bytes z48_logo reads: a nibble a cell, the high nibble
first, cells left to right, rows top to bottom; bit 3 the top left block,
bit 2 the top right, bit 1 the bottom left, bit 0 the bottom right (the
ink's blocks).
"""

G = {  # rows 1-8 of each letter ('#' cyan); the white lines are added
    'N': ["########", "......##", "...#..##", "..##..##", "..##..##", "..##..##", "..##..##", "..##..##"],
    'E': ["######", "......", ".#....", "##....", "######", "##....", "##....", "######"],
    'M': ["##########", "....##..##", ".#..##..##", "##..##..##", "##..##..##", "##..##..##", "##..##..##", "##..##..##"],
    'S': ["######", "......", ".#....", "##....", "######", "....##", "....##", "######"],
    'I': [".#", "##", "##", "##", "##", "##", "##", "##"],
}
WORD, GAP, TAIL = "NEMESIS", 2, 4


def grid():
    """10 rows of 64 blocks: '.', 'C' (cyan) or 'W' (white)."""
    w = sum(len(G[c][0]) for c in WORD) + GAP * (len(WORD) - 1) + TAIL
    q = [['.'] * 64 for _ in range(10)]
    x = (64 - w) // 2 // 2 * 2
    for i, c in enumerate(WORD):
        g = G[c]
        for r in range(8):
            for k in range(len(g[0])):
                if g[r][k] == '#':
                    q[r + 1][x + k] = 'C'
        if i == len(WORD) - 1:                  # the last top bar runs on
            for k in range(len(g[0]), len(g[0]) + TAIL):
                q[1][x + k] = 'C'
        x += len(g[0]) + GAP
    for k in range(64):
        if q[1][k] == 'C':
            q[0][k] = 'W'
        if q[8][k] == 'C':
            q[9][k] = 'W'
    for cc in range(32):                        # no white over a cap narrower than a cell
        if len({q[a][cc * 2 + b] for a in range(2) for b in range(2)}) == 3:
            q[0][cc * 2] = q[0][cc * 2 + 1] = '.'
    return q


def cells():
    """(row, column, nibble, white) for the 160 cells."""
    q = grid()
    out = []
    for cr in range(5):
        for cc in range(32):
            quad = [q[cr * 2 + a][cc * 2 + b] for a in range(2) for b in range(2)]
            assert len(set(quad)) <= 2, ('a colour clash', cr, cc, quad)
            white = 'W' in quad
            if white:
                assert 'C' in quad and '.' not in quad, (cr, cc, quad)
                n = sum(8 >> i for i, v in enumerate(quad) if v == 'W')
                assert (cr, n) in ((0, 0xC), (4, 0x3)), (cr, cc, quad)
            else:
                n = sum(8 >> i for i, v in enumerate(quad) if v == 'C')
            out.append((cr, cc, n, white))
    return out


def data():
    ns = [n for _, _, n, _ in cells()]
    return bytes((ns[i] << 4) | ns[i + 1] for i in range(0, len(ns), 2))


if __name__ == '__main__':
    q = grid()
    print('\n'.join(''.join(r) for r in q))
    print(len(data()), 'bytes')
