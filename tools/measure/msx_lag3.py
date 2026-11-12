"""Input lag on the simulated PAL MSX, measured as lag2.py measures the
Spectrum (0.109): in stage 1 play, up or down is pressed at the start of a
frame (the frame interrupt), and the lag runs to the moment the beam first
draws the ship at its new height.

The TMS9918/9929 raises its frame interrupt at the end of the last line of
the active display (TI, VDP Programmer's Guide, p. 5-5), and reads the
sprite table as it scans.  With 313 lines a frame (PAL: the simulator's
71,364 T-states at 228 a line), the next frame's first active line comes
121 lines after the interrupt, and a sprite at Y is drawn from line Y + 1.
So each frame the sprite table is read at (122 + Y) / 313 of the frame, and
the lag is k + (122 + Y) / 313 for the first frame k whose table, at that
moment, holds the new Y.

Played as msx50.py plays: the port's front end, the ship invulnerable, and
each BIOS call charged an estimate of the real BIOS's time.  The first 40
seconds of play settle (no keys), then trials at varied phases (seed SEED).
usage: msx_lag3.py TRIALS"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, random, statistics
R = os.environ.get('NEM_ROOT', _NEM)
sys.path.insert(0, R + '/reloc'); sys.path.insert(0, R + '/msxsim'); sys.path.insert(0, R + '/spec')
import msxsim
FRAME_T = msxsim.FRAME_T = 71364            # PAL: 313 lines of 228 T-states
import layoutsim as L
from lockstep_spec import patch_front_end
N = int(sys.argv[1])
COST = {'LDIRVM': (100, 57), 'LDIRMV': (100, 57), 'FILVRM': (100, 50), 'WRTVRM': (60, 0), 'RDVRM': (60, 0),
        'WRTVDP': (80, 0), 'WRTPSG': (50, 0), 'RDPSG': (50, 0), 'SNSMAT': (80, 0), 'SETWRT': (60, 0), 'SETRD': (60, 0)}
JOY = [0x3F]
class M(L.Original):
    def bios_call(self, pid, r):
        name = msxsim.NAMES[pid]
        regs = self.sim.registers
        base, per = COST.get(name, (100, 0))
        regs[25] += base + per * ((regs[2] << 8 | regs[3]) if per else 0)
        if name in ('SNSMAT', 'RDPSG'):
            if name == 'SNSMAT':
                fire = self.mem[0xE000] != 5 and (self.frames // 25) % 4 == 0
                r[0] = (0xFE if fire else 0xFF) if r[0] == 8 else 0xFF; return
            if r[0] == 14:
                r[0] = JOY[0]; return
        msxsim.MSX.bios_call(self, pid, r)
m = M(); patch_front_end(m); m.boot()
sim = m.sim; regs = sim.registers; mem = m.mem; ops = sim.opcodes

def run_until(t):
    while regs[25] < t:
        pc = regs[24]
        if pc < 0x4000 and pc not in msxsim.STUB_RANGE:
            raise msxsim.Unknown('execution at %04X' % pc)
        ops[mem[pc]]()
        regs[25] += 1
        if m.int_pending and regs[26]:
            sim.accept_interrupt(regs, mem, pc)
        elif regs[28]:
            regs[25] = max(regs[25], t)

def ship_vram_y():
    sy, sx = m.mem[0xE204], m.mem[0xE206]; v = m.vdp.vram
    best = None
    for i in range(32):
        y = v[0x3B00 + 4 * i]
        if y == 0xD0: break
        x = v[0x3B01 + 4 * i]; p = v[0x3B02 + 4 * i]
        if p in (0, 8, 16) and abs(x - sx) <= 16 and abs(((y + 1) & 255) - sy) <= 16:
            best = y if best is None else min(best, y)
    return best

def frame(sample_y=None):
    """One frame; if sample_y is given, the ship's Y in VRAM when the beam
    reaches line sample_y + 1."""
    start = m.next_int - FRAME_T; seen = None
    if sample_y is not None:
        run_until(start + (122 + sample_y) * FRAME_T // 313)
        seen = ship_vram_y()
    run_until(m.next_int)
    m.vdp.status |= 0x80; m.int_pending = True; m.next_int += FRAME_T; m.frames += 1
    return seen

played = 0
while played < 40 * 50:
    frame()
    if m.mem[0xE000] == 5: played += 1
random.seed(int(os.environ.get('SEED', '7'))); lags = []
for t in range(N):
    JOY[0] = 0x3F
    for i in range(random.randint(10, 40)): frame()
    y0 = ship_vram_y()
    up = m.mem[0xE204] > 0x40
    JOY[0] = 0x3F & ~(1 if up else 2)          # bit 0 up, bit 1 down; 0 = pressed
    for k in range(40):
        y = frame(sample_y=y0)
        if y is not None and y0 is not None and y != y0:
            lags.append(k + (122 + y0) / 313); break
JOY[0] = 0x3F
lags.sort()
print('MSX PAL: %d presses, lag in frames mean %.2f, median %.2f, min %.1f, max %.1f' % (
    len(lags), statistics.mean(lags), statistics.median(lags), min(lags), max(lags)))
