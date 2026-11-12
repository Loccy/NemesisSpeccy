"""The MSX original at 50 Hz through the whole first loop (0.109): as
msx50.py (the port's front end, the ship invulnerable, BIOS time charged),
but with Konami's own all-weapons cheat applied when the first tick in
play ends (3:A0D8,
then 3:A110 for a second option, as lockstep_spec.py's HYPER=1 and the
checkers' NEM_ALL do) and fire on keys_default's rhythm throughout, as the
Spectrum's all-stages runs.  Stops when the second loop's stage 1 starts.
Per stage: seconds of play and ticks a second.
usage: msx_loop.py MAX_SECONDS OUT.json"""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import os, sys, json, collections
R = os.environ.get('NEM_ROOT', _NEM)
sys.path.insert(0, R + '/reloc'); sys.path.insert(0, R + '/msxsim'); sys.path.insert(0, R + '/spec')
import msxsim
msxsim.FRAME_T = 71591                      # as msx50.py
import layoutsim as L
from lockstep_spec import patch_front_end, call_msx
SECS = float(sys.argv[1]); OUT = sys.argv[2]
COST = {'LDIRVM': (100, 57), 'LDIRMV': (100, 57), 'FILVRM': (100, 50), 'WRTVRM': (60, 0), 'RDVRM': (60, 0),
        'WRTVDP': (80, 0), 'WRTPSG': (50, 0), 'RDPSG': (50, 0), 'SNSMAT': (80, 0), 'SETWRT': (60, 0), 'SETRD': (60, 0)}
class M(L.Original):
    def bios_call(self, pid, r):
        name = msxsim.NAMES[pid]
        regs = self.sim.registers
        base, per = COST.get(name, (100, 0))
        regs[25] += base + per * ((regs[2] << 8 | regs[3]) if per else 0)
        if name in ('SNSMAT', 'RDPSG'):
            fire = (self.frames // 25) % 4 == 0
            if name == 'SNSMAT':
                r[0] = (0xFE if fire else 0xFF) if r[0] == 8 else 0xFF; return
            if r[0] == 14:
                r[0] = 0x3F; return
        msxsim.MSX.bios_call(self, pid, r)
m = M(); patch_front_end(m); m.boot()
regs = m.sim.registers; ops = m.sim.opcodes; mem = m.mem
hyper = [False]; last = mem[0xE003]; ticks = 0
start = {}; seen8 = False

def frame():
    """msxsim's run_frame, but applying the cheat when a tick ends in play
    (PC 4054, as lockstep_spec.py calls it), interrupts handled as usual."""
    end = m.next_int
    while regs[25] < end:
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
            regs[25] = max(regs[25], end)
    m.vdp.status |= 0x80; m.int_pending = True; m.next_int += msxsim.FRAME_T; m.frames += 1

played = 0
for f in range(int(SECS * 50)):
    frame()
    c = mem[0xE003]; ticks += (c - last) & 255; last = c
    if mem[0xE000] != 5: continue
    played += 1
    if played % 5000 == 0: print('  %d s of play, stage %d, cheat applied %s' % (played // 50, mem[0xE061], hyper[0]), flush=True)
    st = mem[0xE061]
    if st == 8: seen8 = True
    key = (2 if seen8 and st != 8 else 1, st)   # (loop, stage)
    if key not in start: start[key] = (f, ticks)
    if key[0] == 2: break
ks = sorted(start)
stages = {}
for a, b in zip(ks, ks[1:]):
    (fa, ta), (fb, tb) = start[a], start[b]
    stages[a[1]] = dict(seconds=round((fb - fa) / 50, 1), ticks_per_s=round((tb - ta) / ((fb - fa) / 50), 2))
json.dump(stages, open(OUT, 'w'), indent=1)
print('MSX 50 Hz, first loop:', json.dumps(stages))
