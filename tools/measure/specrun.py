"""The Spectrum build (SNA_DIR), same keys and invulnerability as msx50.py:
per second of play, ticks, distance, stage; and screens shown.
usage: specrun.py SECONDS OUT.json"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, json
sys.path.insert(0, (_NEM + '/spec'))
import emu
from emu import Spectrum
D = os.environ.get('SNA_DIR', (_NEM + '/spec')); SECS = float(sys.argv[1]); OUT = sys.argv[2]
s = Spectrum(D + '/nemesis.sna'); syms = emu._syms(D + '/nemesis.sym'); s.syms = syms
s.mem.banks[0][syms['m1_75F0'] - 0xC000] = 0xC9
def keys(f):
    kb = [0] * 8
    fire = ((f // 25) % 4 == 0) if s.k(0xE000) != 5 else ((f // 2) % 8 < 4)
    if fire: kb[7] |= 1
    return kb
last = s.k(0xE003); rows = []; played = 0; acc = 0; flips = 0; sb = s.tr.out7ffd & 8
for f in range(int(SECS * 50)):
    s.run_frame(keys)
    c = s.k(0xE003); d = (c - last) & 255; last = c
    nb = s.tr.out7ffd & 8
    if s.k(0xE000) == 5:
        played += 1; acc += d; flips += nb != sb
        if played % 50 == 0:
            rows.append((played // 50, acc, s.k(0xE063) | s.k(0xE064) << 8, s.k(0xE061))); acc = 0
    sb = nb
json.dump(rows, open(OUT, 'w'))
t = sum(r[1] for r in rows); print('%s: %d s in play, %.2f ticks/s, %.1f screens/s' % (D, len(rows), t / max(1, len(rows)), flips / max(1, played / 50)))
