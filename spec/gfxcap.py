"""Capture MSX VRAM after Konami's own graphics loaders, per phase, by calling
the loaders directly in the simulator (no gameplay needed)."""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, pickle
sys.path.insert(0, NEM_ROOT + '/reloc'); sys.path.insert(0, NEM_ROOT + '/msxsim')
import msxsim
from layoutsim import Original

def call(m, addr, maxsteps=5_000_000):
    regs = m.sim.registers; ops = m.sim.opcodes; mem = m.mem
    saved = list(regs)
    sp = regs[12] - 2
    mem[sp] = 0xFE; mem[sp + 1] = 0xFF; regs[12] = sp     # return to FFFE (jr $)
    regs[24] = addr; regs[26] = 0                          # no interrupts
    for _ in range(maxsteps):
        pc = regs[24]
        if pc == 0xFFFE:
            regs[:] = saved; return
        if pc < 0x4000 and pc not in msxsim.STUB_RANGE: raise msxsim.Unknown('%04X' % pc)
        ops[mem[pc]]()
        regs[26] = 0
    raise RuntimeError('loader did not return')

def boot_to_idle(ticks=3):
    from layoutsim import vclock_tick
    m = Original(); m.boot()
    for _ in range(ticks): vclock_tick(m)
    return m

if __name__ == '__main__':
    out = {}
    for ph in range(1, 13):
        m = boot_to_idle()
        m.mem[0xE061] = ph
        call(m, 0x422A)
        out[('stage', ph)] = bytes(m.vdp.vram)
        call(m, 0x4A6D)
        out[('expl', ph)] = bytes(m.vdp.vram)
        print(ph, 'ok', flush=True)
    pickle.dump(out, open('vram_states.pkl', 'wb'))
