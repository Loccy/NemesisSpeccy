"""emu.Spectrum on SkoolKit's uncontended simulator (CSimulator): no memory or I/O contention."""
import os as _os; _NEM = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..', '..')); _SCRATCH = _os.environ.get('NEM_SCRATCH') or _os.path.dirname(_NEM)   # the repository, and the folder beside it for working copies
import sys
sys.path.insert(0, (_NEM + '/spec'))
import emu
from skoolkit import CSimulator
from skoolkit.snapshot import Snapshot
from skoolkit.simutils import from_snapshot
from skoolkit.trace import Tracer
import os
class SpectrumNC(emu.Spectrum):
    def __init__(self, path):
        snap = Snapshot.get(path)
        if snap.type == 'SNA' and len(snap.tail) == 0xC000: snap.sp = (snap.sp + 2) % 65536
        self.sim = sim = from_snapshot(CSimulator, snap, {}, {'ay': [None] * 16}, {'fast_djnz': False, 'fast_ldir': False})
        self.mem = sim.memory; self.mem.out7ffd(snap.out7ffd)
        self.tr = Tracer(sim, snap.border, snap.out7ffd, snap.outfffd, list(snap.ay), snap.outfe, False)
        sim.set_tracer(self.tr)
        self.regs = sim.registers; self.pc = snap.pc; self.frame = 0
        self.t0 = self.regs[25]; self.hyper_done = False
        if emu.ALL:
            sym = path[:-4] + '.sym'
            self.syms = emu._syms(sym)
            self.mem.banks[0][self.syms['m1_75F0'] - 0xC000] = 0xC9
