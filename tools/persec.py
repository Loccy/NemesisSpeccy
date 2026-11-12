"""Stage 1 second by second (0.105 fast, scripted play as specrun.py): ticks,
screens shown, distance (E063), sprites in Konami's list; a screenshot a second."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, json
sys.path.insert(0, (_NEM + '/spec'))
import emu
from emu import Spectrum
from emu_bench import scr_png
SNA = sys.argv[1]; SYM = sys.argv[2]; SECS = int(sys.argv[3]); OUT = sys.argv[4]
s = Spectrum(SNA); sy = emu._syms(SYM)
s.mem.banks[0][sy['m1_75F0'] - 0xC000] = 0xC9
b2 = s.mem.banks[2]; at = sy['SPR_ATTR'] - 0x8000
def keys(f):
    kb = [0] * 8
    fire = ((f // 25) % 4 == 0) if s.k(0xE000) != 5 else ((f // 2) % 8 < 4)
    if fire: kb[7] |= 1
    return kb
last = s.k(0xE003); played = 0; rows = []; acc = 0; flips = 0; sb = s.tr.out7ffd & 8; spr = 0
while played < SECS * 50:
    s.run_frame(keys)
    c = s.k(0xE003); d = (c - last) & 255; last = c
    nb = s.tr.out7ffd & 8
    if s.k(0xE000) == 5:
        played += 1; acc += d; flips += nb != sb
        n = 0
        while n < 32 and b2[at + 4 * n] != 0xD0:
            if b2[at + 4 * n + 3] & 15 and b2[at + 4 * n] < 192: spr += 1
            n += 1
        if played % 50 == 0:
            sec = played // 50
            rows.append({'s': sec, 'ticks': acc, 'screens': flips, 'dist': s.k(0xE063) | s.k(0xE064) << 8, 'stage': s.k(0xE061), 'sprites': round(spr / 50, 1)})
            scr_png(s.screen(), '%s/shots/s%03d.png' % (OUT.rsplit('/', 1)[0], sec))
            acc = flips = spr = 0
    sb = nb
json.dump(rows, open(OUT, 'w'))
print('done', len(rows))
