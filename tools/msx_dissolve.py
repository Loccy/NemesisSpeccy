"""Konami's dissolve (3:A6C0) on the MSX simulator, called once per tick as the
boss code does, with msx50.py's BIOS cost model: T-states per call."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys
sys.path.insert(0, (_NEM + '/reloc')); sys.path.insert(0, (_NEM + '/msxsim'))
import msxsim, random
import layoutsim as L
COST = {'LDIRVM': (100, 57), 'LDIRMV': (100, 57)}
class M(L.Original):
    def bios_call(self, pid, r):
        name = msxsim.NAMES[pid]; regs = self.sim.registers
        base, per = COST.get(name, (100, 0))
        regs[25] += base + per * ((regs[2] << 8 | regs[3]) if per else 0)
        msxsim.MSX.bios_call(self, pid, r)
m = M(); mem = m.mem; regs = m.sim.registers; ops = m.sim.opcodes
random.seed(1)
for a in range(0x4000): m.vdp.vram[a] = random.randrange(256)
mem.bank[2] = 3; mem.bank[1] = 2                  # bank 3 at A000 (and 2 at 8000)
mem[0xE1A0] = 0; mem[0xE1D0] = 1                    # step 0; a sound already playing (skip the request)
mem[0xFFFE] = 0x18; mem[0xFFFF] = 0xFE
mem.bank[2] = 3; mem.bank[1] = 2
calls = []
for n in range(80):
    sp = 0xF000; mem[sp] = 0xFE; mem[sp + 1] = 0xFF
    regs[12] = sp; regs[24] = 0xA6C0; t0 = regs[25]
    while regs[24] != 0xFFFE:
        ops[mem[regs[24]]](); regs[25] += 1
    calls.append((mem[0xE1A0], regs[25] - t0))
    if mem[0xE1A3]: break
print(len(calls), 'calls')
print(calls)
