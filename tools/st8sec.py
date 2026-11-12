"""All-stages route (NEM_ALL, NEM_TARGETS): ticks a second and a screenshot a
second from FROM to TO seconds of play."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys, json
sys.path.insert(0, (_NEM + '/spec'))
import emu
from emu import Spectrum
from emu_bench import scr_png
D, A, B, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
s = Spectrum(D + '/nemesis.sna'); s.syms = emu._syms(D + '/nemesis.sym')
played = 0; last = s.k(0xE003); acc = 0; flips = 0; sb = s.tr.out7ffd & 8; rows = []
while played < B * 50:
    s.run_frame()
    c = s.k(0xE003); d = (c - last) & 255; last = c; nb = s.tr.out7ffd & 8
    if s.k(0xE000) == 5:
        played += 1
        if played > A * 50:
            acc += d; flips += nb != sb
            if played % 50 == 0:
                sec = played // 50
                rows.append({'s': sec, 'ticks': acc, 'screens': flips, 'stage': s.k(0xE061)}); acc = flips = 0
                scr_png(s.screen(), '%s/s%04d.png' % (OUT.rsplit('/', 1)[0] + '/shots', sec))
    sb = nb
json.dump(rows, open(OUT, 'w')); print('done')
