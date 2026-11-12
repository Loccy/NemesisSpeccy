import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys
R=_NEM
sys.path.insert(0, R + '/reloc'); sys.path.insert(0, R + '/msxsim'); sys.path.insert(0, R + '/spec')
import msxsim, layoutsim as L
from lockstep_spec import patch_front_end, call_msx
class M(L.Original):
    def bios_call(self, pid, r):
        name = msxsim.NAMES[pid]
        if name == 'SNSMAT':
            fire = (self.frames // 25) % 4 == 0
            r[0] = (0xFE if fire else 0xFF) if r[0] == 8 else 0xFF; return
        if name == 'RDPSG' and r[0] == 14: r[0] = 0x3F; return
        msxsim.MSX.bios_call(self, pid, r)
m = M(); patch_front_end(m); m.boot()
regs = m.sim.registers; ops = m.sim.opcodes; mem = m.mem
while True:
    m.run_frame()
    if mem[0xE000] == 5: break
# run until pc 4054
done=[None]
end = m.next_int
while done[0] is None:
    pc = regs[24]
    if pc == 0x4054 and mem[0xE000] == 5:
        a = bytes(mem[i] for i in range(0xC000,0x10000)); call_msx(m, 0xA0D8); call_msx(m, 0xA110); b = bytes(mem[i] for i in range(0xC000,0x10000)); done[0]=1; break
    ops[mem[pc]](); regs[25] += 1
    if m.int_pending and regs[26]: m.sim.accept_interrupt(regs, mem, pc)
    elif regs[28]: regs[25] = max(regs[25], end)
    if regs[25] >= end:
        m.vdp.status |= 0x80; m.int_pending = True; m.next_int += msxsim.FRAME_T; m.frames += 1; end = m.next_int
d = [(0xC000+i, a[i], b[i]) for i in range(len(a)) if a[i] != b[i]]
print(len(d)); print([( '%04X'%x, '%02X'%p, '%02X'%q) for x,p,q in d])
