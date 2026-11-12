"""The MSX original at 50 Hz through the first loop, played as pp_feel.py
plays the 128K (perfprofile.py LOOP=1 with NEM_ALL=1): invulnerable,
Konami's all-weapons cheat once play starts, keys_default's fire rhythm, and
every 97 frames in play a press of up or down towards the middle, held until
the screen shows the ship moved.  BIOS time charged as msx_loop.py.

The picture: the VDP shows VRAM as the beam scans it.  Each frame is sampled
when the beam reaches the middle of the play area (line 96 of the display,
122 + 96 lines after the frame interrupt, as msx_lag3.py), and what it shows
is taken from the last write to the sprite attribute table (3B00-3B7F) before
then: the tick count at that write.  The ship's Y is read from VRAM at the
sample.  Writes a timeline per frame, as pp_feel.py does.
usage: msx_feel.py MAX_SECONDS OUT"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, json, pickle
R = _NEM
sys.path.insert(0, R + '/reloc'); sys.path.insert(0, R + '/msxsim'); sys.path.insert(0, R + '/spec')
import msxsim
import layoutsim as L
from lockstep_spec import patch_front_end, call_msx
FRAME_T = msxsim.FRAME_T = 71591
SECS = float(sys.argv[1]); OUT = sys.argv[2]
COST = {'LDIRVM': (100, 57), 'LDIRMV': (100, 57), 'FILVRM': (100, 50), 'WRTVRM': (60, 0), 'RDVRM': (60, 0),
        'WRTVDP': (80, 0), 'WRTPSG': (50, 0), 'RDPSG': (50, 0), 'SNSMAT': (80, 0), 'SETWRT': (60, 0), 'SETRD': (60, 0)}
JOY = [0x3F]
ST = dict(ticks=0, last=0, sat_tick=None, sat_writes=0, sat_time=0)

class M(L.Original):
    def bios_call(self, pid, r):
        name = msxsim.NAMES[pid]
        regs = self.sim.registers
        base, per = COST.get(name, (100, 0))
        regs[25] += base + per * ((regs[2] << 8 | regs[3]) if per else 0)
        if name in ('SNSMAT', 'RDPSG'):
            if name == 'SNSMAT':
                fire = (self.frames // 25) % 4 == 0
                r[0] = (0xFE if fire else 0xFF) if r[0] == 8 else 0xFF; return
            if r[0] == 14:
                r[0] = JOY[0]; return
        if name in ('LDIRVM', 'WRTVRM', 'FILVRM'):
            de = r[5] + 256 * r[4]; hl = r[7] + 256 * r[6]
            a = de if name == 'LDIRVM' else hl
            if 0x3B00 <= (a & 0x3FFF) < 0x3B80: sat_written()
        msxsim.MSX.bios_call(self, pid, r)

m = M(); patch_front_end(m); m.boot()
regs = m.sim.registers; ops = m.sim.opcodes; mem = m.mem; vdp = m.vdp
ST['last'] = mem[0xE003]

def count_ticks():
    c = mem[0xE003]; ST['ticks'] += (c - ST['last']) & 255; ST['last'] = c

def sat_written():
    count_ticks(); ST['sat_tick'] = ST['ticks']; ST['sat_writes'] += 1

_wd = vdp.write_data
def wd(v, _wd=_wd):
    if 0x3B00 <= vdp.addr < 0x3B80: sat_written()
    _wd(v)
vdp.write_data = wd

hyper = [False]
def run_until(t):
    while regs[25] < t:
        pc = regs[24]
        if pc == 0x4054 and not hyper[0] and mem[0xE000] == 5:
            call_msx(m, 0xA0D8); call_msx(m, 0xA110); hyper[0] = True
        if pc < 0x4000 and pc not in msxsim.STUB_RANGE:
            raise msxsim.Unknown('execution at %04X' % pc)
        ops[mem[pc]]()
        regs[25] += 1
        if m.int_pending and regs[26]:
            m.sim.accept_interrupt(regs, mem, pc)
        elif regs[28]:
            regs[25] = max(regs[25], t)

def ship_vram_y():
    sy, sx = mem[0xE204], mem[0xE206]; v = vdp.vram
    best = None
    for i in range(32):
        y = v[0x3B00 + 4 * i]
        if y == 0xD0: break
        x = v[0x3B01 + 4 * i]; p = v[0x3B02 + 4 * i]
        if p in (0, 8, 16) and abs(x - sx) <= 16 and abs(((y + 1) & 255) - sy) <= 16:
            best = y if best is None else min(best, y)
    return best

SAMPLE = 122 + 96
LAG_EVERY = 97
TL = []; lag = []; press = None; next_press = 0
start = {}; seen8 = False
for f in range(int(SECS * 50)):
    in_play = mem[0xE000] == 5
    if in_play and press is None and f >= next_press:
        y0 = ship_vram_y()
        if y0 is not None:
            press = (f, y0, 'up' if y0 >= 90 else 'down')
    if press is not None and f - press[0] > 50:
        press = None; next_press = f + LAG_EVERY
    JOY[0] = 0x3F if press is None else 0x3F & ~(1 if press[2] == 'up' else 2)
    t0 = m.next_int - FRAME_T
    if press is not None:
        # with a press under way, sampled where the beam reaches the ship's
        # line (as msx_lag3.py), the picture's tick at line 96 kept apart
        ln = 122 + press[1]
        if ln > SAMPLE:
            run_until(t0 + SAMPLE * FRAME_T // 313); shown = ST['sat_tick']
            run_until(t0 + ln * FRAME_T // 313); y = ship_vram_y()
        else:
            run_until(t0 + ln * FRAME_T // 313); y = ship_vram_y()
            run_until(t0 + SAMPLE * FRAME_T // 313); shown = ST['sat_tick']
    else:
        run_until(t0 + SAMPLE * FRAME_T // 313)
        y = ship_vram_y(); shown = ST['sat_tick']
    if press is not None and y is not None and y != press[1]:
        lag.append(f - press[0] + (122 + press[1]) / 313)
        press = None; next_press = f + 1 + LAG_EVERY
    run_until(m.next_int)
    vdp.status |= 0x80; m.int_pending = True; m.next_int += FRAME_T; m.frames += 1
    count_ticks()
    st = mem[0xE061]
    if in_play:
        if st == 8: seen8 = True
        key = (2 if seen8 and st != 8 else 1, st)
        if key not in start: start[key] = (f, ST['ticks'])
        if key[0] == 2: break
    TL.append((f, int(in_play), st, shown, y, ST['ticks'], mem[0xE063] | mem[0xE064] << 8, int(press is not None)))
    if f % 5000 == 0: print(f, st, ST['ticks'], ST['sat_writes'], len(lag), flush=True)
pickle.dump(dict(TL=TL, lag=lag, stage_start=start), open(OUT + '.tl.pkl', 'wb'))
print('done', len(TL), len(lag), start)
