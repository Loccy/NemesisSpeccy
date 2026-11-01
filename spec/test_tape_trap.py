"""Load nemesis.tap the way a DivMMC does from its card: the ROM's LD-BYTES
is trapped at 0562 and each block put straight into memory.  The machine
state at the loader's start comes from tap2sna (-s 0x4000, run here).  The trap
returns either by RET (mode ret) or through the ROM's SA/LD-RET at 053F,
which enables interrupts (mode sald; the frame interrupt is then made due
just around that EI, so the loader's IM 2 handler is exercised).  At
plat_boot the memory must equal nemesis.sna's outside the screens.
usage: test_tape_trap.py ret|sald"""
import os, sys, re, subprocess, tempfile
NEM_ROOT = os.environ.get('NEM_ROOT') or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
sys.path.insert(0, NEM_ROOT + '/w31/tools')
from skoolkit.snapshot import Snapshot
from skoolkit.simutils import from_snapshot
from skoolkit import CCMIOSimulator
from skoolkit.trace import Tracer
D = NEM_ROOT + '/spec'; MODE = sys.argv[1]
S = tempfile.mkdtemp()
subprocess.run(['sjasmplus', '--nologo', '--msg=war', '--sym=tape/loader.sym', 'tape/loader.asm'], cwd=D, check=True, capture_output=True)
subprocess.run(['tap2sna.py', '-c', 'machine=128', '-s', '0x4000', D + '/nemesis.tap', S + '/at_loader.z80'], check=True, capture_output=True)
FRAME = 70908
syms = {}
for l in open(D + '/nemesis.sym'):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: syms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
lsyms = {}
for l in open(D + '/tape/loader.sym'):
    m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
    if m: lsyms[m.group(1)] = int(m.group(2), 16) & 0xFFFF
RET = lsyms['load.ret']
tap = open(D + '/nemesis.tap', 'rb').read(); blocks = []; i = 0
while i < len(tap):
    n = tap[i] | tap[i + 1] << 8; blocks.append(tap[i + 2:i + 2 + n]); i += 2 + n
blocks = blocks[4:]                                   # after BASIC and the loader
snap = Snapshot.get(S + '/at_loader.z80')
sim = from_snapshot(CCMIOSimulator, snap, {}, {'ay': [None] * 16}, {'fast_djnz': False, 'fast_ldir': False})
mem = sim.memory; mem.out7ffd(snap.out7ffd)
tr = Tracer(sim, snap.border, snap.out7ffd, snap.outfffd, list(snap.ay), snap.outfe, False)
sim.set_tracer(tr); r = sim.registers
pc = snap.pc; served = 0; taken = 0
import random; random.seed(1)
while True:
    stop = 0x0562 if served < len(blocks) else syms['plat_boot']
    sim.trace(pc, stop, 0, r[25] + FRAME * 3000, 1, None, None, None, None, None); pc = r[24]
    if pc != stop: sys.exit('did not reach %04X (PC %04X)' % (stop, pc))
    if stop == syms['plat_boot']: break
    b = blocks[served]; served += 1
    ix = r[8] << 8 | r[9]; de = r[4] << 8 | r[5]; flag = r[16]
    assert b[0] == flag and len(b) - 2 == de, (served, b[0], flag, len(b) - 2, de)
    for k in range(de): mem[(ix + k) & 0xFFFF] = b[1 + k]
    ix = (ix + de) & 0xFFFF; r[8], r[9] = ix >> 8, ix & 255; r[4] = r[5] = 0; r[1] |= 1   # carry: loaded
    if MODE == 'ret':
        sp = r[12]; pc = mem[sp] | mem[(sp + 1) & 0xFFFF] << 8; r[12] = (sp + 2) & 0xFFFF
    else:
        pc = 0x053F
        t = r[25]; r[25] = (t // FRAME + 1) * FRAME - random.randint(60, 140)   # the frame interrupt due around the EI
        sim.trace(pc, 0xBEBE, 0, r[25] + 400, 1, None, None, None, None, None); pc = r[24]
        if pc == 0xBEBE: taken += 1
    r[24] = pc
B = Snapshot.get(D + '/nemesis.sna').memory.banks
bad = sum(1 for k in range(8) for i in range(16384) if not (k in (5, 7) and i < 0x1B00) and mem.banks[k][i] != B[k][i]) if hasattr(mem, 'banks') else None
print('mode %s: %d blocks served, interrupt handler run %d times, reached plat_boot; differing bytes outside the screens: %s' % (MODE, served, taken, bad))
