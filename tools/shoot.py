"""Screenshots: title frames, then one per second of play from A to B."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys
sys.path.insert(0, (_NEM + '/spec'))
import emu
from emu import Spectrum
from emu_bench import scr_png
D, A, B, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
s = Spectrum(D + '/nemesis.sna'); s.syms = emu._syms(D + '/nemesis.sym')
played = 0; f = 0
while played < B * 50:
    s.run_frame(); f += 1
    if s.k(0xE000) == 5:
        played += 1
        if played >= A * 50 and played % 50 == 0:
            scr_png(s.screen(), '%s/p%04d_s%02d.png' % (OUT, played // 50, s.k(0xE061)))
    elif played == 0 and f % 50 == 0 and f <= 600:
        scr_png(s.screen(), '%s/title_f%04d.png' % (OUT, f))
print('done')
