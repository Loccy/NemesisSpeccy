"""Where the 128K's input lag goes (10 November 2026).  The shipped build in
the Spectrum simulator, the first loop with all weapons (NEM_ALL=1), fire on
keys_default's rhythm and, every 97 frames in play, a press of up or down
towards the middle held until the screen shows the ship moved, as
perfprofile.py.  For each press, from the start of the frame it begins:
  read:   Konami's ship Y (E204) changes (the tick that read the press);
  render: the next pm_render (a screen drawn with the moved ship);
  done:   flip_pending set (that screen finished, waiting to be shown);
  shown:  the frame whose interrupt shows it, plus the beam's way down to
          the ship's line (64 + Y lines of 312), as perfprofile.py counts.
Times in frames (70,908 T-states)."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, pickle, statistics as S
sys.path.insert(0, (_NEM + '/spec'))
from emu import Spectrum, _syms, keys_default
s = Spectrum(sys.argv[1]); sy = _syms(sys.argv[2]); PMW = sy['pm_wait']
s.mem.banks[0][sy['m1_75F0'] - 0xC000] = 0xC9
sim = s.sim; R = s.regs; tr = s.tr; FR = 70908; PMR = sy['pm_render']; FP = sy['flip_pending']
SPR = 0xEC80; SL = 500
def ship_y():
    for i in range(32):
        y = s.k(SPR + 4 * i); p = s.k(SPR + 4 * i + 2)
        if y == 0xD0: break
        if p in (0, 8, 16): return y
    return None
def fx(a): return s.mem.banks[2][a - 0x8000]
press = None; next_press = 0; out = []; cur = None
disp = tr.out7ffd & 8; seen8 = False; stg_done = False
for f in range(int(float(sys.argv[3]) * 50)):
    in_play = s.k(0xE000) == 5
    kb = keys_default(f)
    if in_play and press is None and f >= next_press:
        y0 = s.k(0xE204)
        if y0: press = dict(f=f, t0=s.t0 + f * FR, y0=y0, d='A' if y0 < 90 else 'Q')
    if press:
        if press['d'] == 'Q': kb[2] |= 1
        else: kb[1] |= 1
    s.hook(advance=True); tr.keyboard = kb
    end = s.t0 + (f + 1) * FR
    while R[25] < end:
        tgt = PMW if (press and 'read' in press and 'wait' not in press) else PMR
        sim.trace(s.pc, tgt, 0, min(end, R[25] + SL), 1, None, None, None, None, None); s.pc = R[24]
        if s.pc == PMW and tgt == PMW and press and 'read' in press:
            press['wait'] = R[25]; press['tk1'] = s.k(0xE003)
            sim.trace(s.pc, -1, 1, end, 1, None, None, None, None, None); s.pc = R[24]
            continue
        if press:
            if 'read' not in press and s.k(0xE204) != press['y0']:
                press['read'] = R[25]; press['tk0'] = s.k(0xE003)
            elif 'read' in press and 'render' in press and 'done' not in press and fx(FP):
                press['done'] = R[25]
        if s.pc == PMR:
            if press and 'read' in press and 'render' not in press:
                press['render'] = R[25]; press['scr'] = (tr.out7ffd & 8) ^ 8; press['y'] = ship_y()
            sim.trace(s.pc, -1, 1, end, 1, None, None, None, None, None); s.pc = R[24]
    s.frame = f + 1
    d = tr.out7ffd & 8
    if press and 'done' in press and d != disp and d == press['scr']:
        press['shown'] = s.t0 + f * FR + (64 + ((press['y'] or 0) + 1) % 256) * FR / 312
        out.append(press); press = None; next_press = f + 1 + 97
    disp = d
    if press and f - press['f'] > 60: press = None; next_press = f + 97
    st = s.k(0xE061)
    if in_play:
        if st == 8: seen8 = True
        if seen8 and st != 8: break
pickle.dump(out, open(sys.argv[4], 'wb'))
def m(a, b): return [(p[b] - p[a]) / FR for p in out]
print('presses', len(out))
print('extra ticks before drawing: mean %.2f' % S.mean([(p['tk1'] - p['tk0']) & 255 for p in out]))
for a, b, name in (('t0', 'read', 'press -> the tick moves the ship'), ('read', 'wait', '-> tick and pacing done'), ('wait', 'render', '-> drawing starts (the wait)'), ('read', 'render', '-> its screen starts drawing'),
                   ('render', 'done', 'drawing'), ('done', 'shown', '-> shown (to the ship\'s line)'), ('t0', 'shown', 'total')):
    v = m(a, b); print('%-36s mean %.2f  median %.2f  90%% %.2f' % (name, S.mean(v), S.median(v), sorted(v)[int(len(v) * .9)]))
