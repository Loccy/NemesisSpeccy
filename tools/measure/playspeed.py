"""Ticks per second in play (Konami state 5), per 5-second window, with the
stage and the scroll distance, on the release build.  Workloads:
  hyper: invulnerable, Konami's HYPER (all weapons, 2 options), fire 1 s in 4
  plain: invulnerable, no power-ups, fire tapped (4 ticks on, 4 off)
usage: playspeed.py WORKLOAD SECONDS"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys
WL, SECS = sys.argv[1], float(sys.argv[2])
if WL == 'hyper': os.environ['NEM_ALL'] = '1'
sys.path.insert(0, (_NEM + '/spec'))
import emu
from emu import Spectrum, keys_default
s = Spectrum((_NEM + '/spec/nemesis.sna'))
if WL != 'hyper':
    s.syms = emu._syms((_NEM + '/spec/nemesis.sym'))
    s.mem.banks[0][s.syms['m1_75F0'] - 0xC000] = 0xC9      # invulnerable
def keys(f):
    kb = [0] * 8
    if WL == 'hyper' or s.k(0xE000) != 5:
        return keys_default(f)
    if (f // 2) % 8 < 4: kb[7] |= 1
    return kb
last = s.k(0xE003); win = []; ticks = 0; frames = 0; total_t = total_f = 0
for f in range(int(SECS * 50)):
    s.run_frame(keys)
    c = s.k(0xE003); d = (c - last) & 255; last = c
    if s.k(0xE000) == 5:
        ticks += d; frames += 1; total_t += d; total_f += 1
    if frames == 250:
        dist = s.k(0xE063) | s.k(0xE064) << 8
        win.append('%.1f(st%d,%03X)' % (ticks / 5, s.k(0xE061), dist)); ticks = frames = 0
print(WL, 'in play %.1f s, %.2f ticks/s' % (total_f / 50, total_t / (total_f / 50)))
print(' '.join(win))
