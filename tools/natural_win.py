"""Website screenshots: the ship steered along a weaving path (so the options
trail it), firing, invulnerable with Konami's own all-weapons cheat (NEM_ALL),
no targets touched.  Every 5 frames of play, the frame is scored: sprite cells
over terrain or over another sprite of a different colour count as clash.  The
busiest clash-free frame in each 4-second window is saved."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, json, math
sys.path.insert(0, (_NEM + '/spec'))
import emu
from emu import Spectrum
from emu_bench import scr_png
D, SECS, OUT, PHASE = sys.argv[1], int(sys.argv[2]), sys.argv[3], float(sys.argv[4])
WINS = [tuple(map(int, w.split('-'))) for w in sys.argv[5].split(',')] if len(sys.argv) > 5 else []
s = Spectrum(D + '/nemesis.sna'); sy = emu._syms(D + '/nemesis.sym'); s.syms = sy
b2 = s.mem.banks[2]; AT = sy['SPR_ATTR'] - 0x8000; NS = sy['name_shadow'] - 0x8000
played = 0
def keys(f):
    kb = [0] * 8
    if s.k(0xE000) != 5:
        if (f // 25) % 4 == 0: kb[7] |= 1
        return kb
    if (f // 2) % 8 < 4: kb[7] |= 1                     # fire
    t = played / 50.0 + PHASE
    ty = 92 + 58 * math.sin(2 * math.pi * t / 5.3)
    tx = 85 + 50 * math.sin(2 * math.pi * t / 11.0)
    y, x = s.k(0xE204), s.k(0xE206)
    if y < ty - 3: kb[1] |= 1                            # A down
    elif y > ty + 3: kb[2] |= 1                          # Q up
    if x < tx - 3: kb[5] |= 1                            # P right
    elif x > tx + 3: kb[5] |= 2                          # O left
    return kb
b7 = s.mem.banks[7]; SP = sy['SPR_PAT'] - 0xC000; SH = sy['ship_pat'] - 0x8000
def pat_bytes(p):
    if p < 24:
        if p & 4: return None
        return bytes(b2[SH + (p // 8) * 32: SH + (p // 8) * 32 + 32])
    return bytes(b7[SP + p * 8: SP + p * 8 + 32])
def score():
    """Clash: a cell holding pixels of two differently coloured sprites, or
    sprite pixels over terrain (a cell whose name is not blank or a star)."""
    cells = {}; n = 0
    for i in range(32):
        y = b2[AT + 4 * i]
        if y == 0xD0: break
        x, p, c = b2[AT + 4 * i + 1], b2[AT + 4 * i + 2], b2[AT + 4 * i + 3]
        col = c & 15
        if not col or y >= 191: continue
        if c & 0x80: x -= 32
        data = pat_bytes(p & 0xFC)
        if data is None: continue
        n += 1
        for h in range(2):
            for r in range(16):
                v = data[h * 16 + r]
                if not v: continue
                py = y + 1 + r
                if py < 0 or py >= 176: continue
                xo = x + h * 8
                for bit in range(8):
                    if v & (128 >> bit):
                        px = xo + bit
                        if 0 <= px < 256:
                            cells.setdefault((py >> 3, px >> 3), set()).add(col)
    clash = 0
    for (cy, cx), cs in cells.items():
        if len(cs) > 1 or b2[NS + cy * 32 + cx] not in (0, 0xF6, 0xF7): clash += 1
    terr = sum(1 for c in range(22 * 32) if b2[NS + c] not in (0, 0xF6, 0xF7))
    return clash, n, terr
best = {}; meta = []
while played < SECS * 50:
    s.run_frame(keys)
    if s.k(0xE000) != 5: continue
    played += 1
    if played % 5: continue
    if WINS:
        if played % 10 == 0 and any(a * 50 <= played < b * 50 for a, b in WINS):
            clash, n, terr = score()
            scr_png(s.screen(), '%s/f%06d_c%02d_n%02d_s%02d.png' % (OUT, played, clash, n, s.k(0xE061)))
        continue
    clash, n, terr = score()
    if clash: continue
    w = played // 200
    sc = n * 10 + terr / 20
    if n >= 3 and (w not in best or sc > best[w][0]):
        best[w] = (sc, played, s.k(0xE061), n, terr)
        scr_png(s.screen(), '%s/w%04d.png' % (OUT, w))
json.dump({w: v for w, v in best.items()}, open(OUT + '/meta.json', 'w'))
print('done', len(best))
