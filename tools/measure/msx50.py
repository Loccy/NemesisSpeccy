"""The MSX original at 50 Hz (frames of 71,591 T-states), invulnerable, with
the Spectrum build's front end, played with the same frame-based keys as
playspeed.py's 'plain' workload.  BIOS calls are stubs in the simulator, so
each is charged an estimate of the real BIOS's time (VRAM block moves at
57 T-states a byte).  Writes, per second of play: ticks, distance, state.
usage: msx50.py SECONDS OUT.json"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, json
sys.path.insert(0, (_NEM + '/reloc')); sys.path.insert(0, (_NEM + '/msxsim')); sys.path.insert(0, (_NEM + '/spec'))
import msxsim
msxsim.FRAME_T = 71591
import layoutsim as L
from lockstep_spec import patch_front_end
SECS = float(sys.argv[1]); OUT = sys.argv[2]
COST = {'LDIRVM': (100, 57), 'LDIRMV': (100, 57), 'FILVRM': (100, 50), 'WRTVRM': (60, 0), 'RDVRM': (60, 0),
        'WRTVDP': (80, 0), 'WRTPSG': (50, 0), 'RDPSG': (50, 0), 'SNSMAT': (80, 0), 'SETWRT': (60, 0), 'SETRD': (60, 0)}
class M(L.Original):
    def bios_call(self, pid, r):
        name = msxsim.NAMES[pid]
        regs = self.sim.registers
        base, per = COST.get(name, (100, 0))
        n = (regs[2] << 8 | regs[3]) if per else 0
        regs[25] += base + per * n
        if name in ('SNSMAT', 'RDPSG'):
            f = self.frames
            if self.mem[0xE000] != 5: fire = (f // 25) % 4 == 0
            else: fire = (f // 2) % 8 < 4
            if name == 'SNSMAT':
                r[0] = (0xFE if fire else 0xFF) if r[0] == 8 else 0xFF; return
            if r[0] == 14:
                r[0] = 0x3F; return
        msxsim.MSX.bios_call(self, pid, r)
m = M(); patch_front_end(m); m.boot()
last = m.mem[0xE003]; rows = []; played = 0; tick_acc = 0
for f in range(int(SECS * 50)):
    m.run_frame()
    c = m.mem[0xE003]; d = (c - last) & 255; last = c
    if m.mem[0xE000] == 5:
        played += 1; tick_acc += d
        if played % 50 == 0:
            rows.append((played // 50, tick_acc, m.mem[0xE063] | m.mem[0xE064] << 8, m.mem[0xE061])); tick_acc = 0
json.dump(rows, open(OUT, 'w'))
t = sum(r[1] for r in rows); print('MSX 50 Hz: %d s in play, %.2f ticks/s' % (len(rows), t / max(1, len(rows))))
