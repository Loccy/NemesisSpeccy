"""Minimal MSX1 for running the unmodified Nemesis cartridge.

Z80: SkoolKit's Python simulator (full instruction set).
Mapper: Konami4 (no SCC), 8KB windows at 4000 (fixed bank 0), 6000, 8000, A000.
VDP: TMS9918 port model (VRAM, registers, address latch, status flag).
BIOS: only the entry points Nemesis uses (see survey).  Each is a stub
'OUT (id),A : RET' handled in Python; RST 20h (DCOMPR) and the interrupt
handler at 0038 are real Z80.  Executing anywhere else below 4000 raises.
Timing: 60Hz frames of 59,736 T, plus one wait state per instruction fetch
(MSX M1 wait, approximated per instruction).
"""
from skoolkit.simulator import Simulator

FRAME_T = 59736          # 3,579,545 Hz / 59.92 Hz

class Unknown(Exception):
    pass

BIOS = {  # address: (port id, name)
    0x000C: (1, 'RDSLT'), 0x0024: (2, 'ENASLT'), 0x0047: (3, 'WRTVDP'),
    0x004D: (4, 'WRTVRM'), 0x0053: (5, 'SETWRT'), 0x0056: (6, 'FILVRM'),
    0x0059: (7, 'LDIRMV'), 0x005C: (8, 'LDIRVM'), 0x0093: (9, 'WRTPSG'),
    0x0096: (10, 'RDPSG'), 0x0138: (11, 'RSLREG'), 0x013E: (12, 'RDVDP'),
    0x0141: (13, 'SNSMAT'),
}
NAMES = {pid: name for _, (pid, name) in BIOS.items()}

class Memory:
    def __init__(self, rom, bios):
        self.rom = rom
        self.bios = bios
        self.ram = bytearray(0x4000)
        self.bank = [0, 1, 2, 3]
        self.mapper_log = None

    def __len__(self):
        return 0x10000

    def __getitem__(self, a):
        if a >= 0xC000:
            return self.ram[a - 0xC000]
        if a >= 0x4000:
            w = (a - 0x4000) >> 13
            return self.rom[(self.bank[w] << 13) | (a & 0x1FFF)]
        return self.bios[a]

    def __setitem__(self, a, v):
        if a >= 0xC000:
            self.ram[a - 0xC000] = v
        elif 0x6000 <= a < 0xC000:
            w = (a - 0x4000) >> 13
            self.bank[w] = v & 15
            if self.mapper_log is not None:
                self.mapper_log.append((a & 0xE000, v))

class VDP:
    def __init__(self):
        self.vram = bytearray(0x4000)
        self.reg = [0] * 8
        self.addr = 0
        self.latch = None
        self.read_buf = 0
        self.status = 0

    def write_data(self, v):
        self.vram[self.addr] = v
        self.addr = (self.addr + 1) & 0x3FFF
        self.latch = None

    def write_ctrl(self, v):
        if self.latch is None:
            self.latch = v
            return
        lo, self.latch = self.latch, None
        if v & 0x80:
            self.reg[v & 7] = lo
        else:
            self.addr = lo | ((v & 0x3F) << 8)
            if not v & 0x40:
                self.read_buf = self.vram[self.addr]
                self.addr = (self.addr + 1) & 0x3FFF

    def read_data(self):
        v = self.read_buf
        self.read_buf = self.vram[self.addr]
        self.addr = (self.addr + 1) & 0x3FFF
        self.latch = None
        return v

    def read_status(self):
        v = self.status
        self.status &= 0x1F
        self.latch = None
        return v

def make_bios():
    b = bytearray([0x76]) * 0x4000           # HALT everywhere: caught as unknown
    b[0x0006] = 0x98                          # VDP read port
    b[0x0007] = 0x98                          # VDP write port
    for addr, (pid, _) in BIOS.items():
        b[addr:addr + 3] = bytes([0xD3, pid, 0xC9])          # OUT (pid),A : RET
    b[0x0020:0x0026] = bytes([0x7C, 0x92, 0xC0, 0x7D, 0x93, 0xC9])  # DCOMPR
    # IM1 handler: save everything, H.KEYI, H.TIMI, restore.
    handler = bytes([
        0xE5, 0xD5, 0xC5, 0xF5, 0xD9, 0x08, 0xE5, 0xD5, 0xC5, 0xF5,
        0xFD, 0xE5, 0xDD, 0xE5,
        0xCD, 0x9A, 0xFD,             # call H.KEYI
        0xCD, 0x9F, 0xFD,             # call H.TIMI
        0xDD, 0xE1, 0xFD, 0xE1,
        0xF1, 0xC1, 0xD1, 0xE1, 0x08, 0xD9, 0xF1, 0xC1, 0xD1, 0xE1, 0xFB, 0xC9])
    b[0x0038:0x003B] = bytes([0xC3, 0x00, 0x3F])          # JP 3F00, as a real BIOS jumps away
    b[0x3F00:0x3F00 + len(handler)] = handler
    assert len(b) == 0x4000
    return b

STUB_RANGE = {a + i for a in BIOS for i in range(3)} | set(range(0x20, 0x26)) | set(range(0x38, 0x3B)) | set(range(0x3F00, 0x3F00 + 36))

class MSX:
    def __init__(self, rom):
        self.mem = Memory(rom, make_bios())
        self.vdp = VDP()
        self.psg = [0] * 16
        self.keys = [0xFF] * 11              # keyboard rows, 0 = pressed
        self.joy = 0x3F                      # PSG reg 14: bits 0-5, 0 = pressed
        self.bios_calls = {}
        self.ports_out = {}
        ram = self.mem.ram
        for a in range(0xFD9A, 0xFFCA):      # BIOS hooks default to RET
            ram[a - 0xC000] = 0xC9
        self.sim = Simulator(self.mem, {'SP': 0xF380})
        self.sim.set_tracer(self)
        self.frames = 0
        self.next_int = FRAME_T
        self.int_pending = False

    # --- tracer interface -------------------------------------------------
    def read_port(self, registers, port):
        p = port & 0xFF
        if p == 0x98:
            return self.vdp.read_data()
        if p == 0x99:
            self.int_pending = False
            return self.vdp.read_status()
        if p == 0xA2:
            return self.joy if self.psg_reg == 14 else self.psg[self.psg_reg]
        return 0xFF

    psg_reg = 0

    def write_port(self, registers, port, value, offset):
        p = port & 0xFF
        if p == 0x98:
            self.vdp.write_data(value)
        elif p == 0x99:
            self.vdp.write_ctrl(value)
        elif p == 0xA0:
            self.psg_reg = value & 15
        elif p == 0xA1:
            self.psg[self.psg_reg] = value
        elif 1 <= p <= 13 and registers[24] in STUB_RANGE:
            self.bios_call(p, registers)
        else:
            self.ports_out[p] = self.ports_out.get(p, 0) + 1

    def bios_call(self, pid, r):
        name = NAMES[pid]
        self.bios_calls[name] = self.bios_calls.get(name, 0) + 1
        A, B, C, D, E, H, L = 0, 2, 3, 4, 5, 6, 7
        hl = r[L] + 256 * r[H]; de = r[E] + 256 * r[D]; bc = r[C] + 256 * r[B]
        v = self.vdp; m = self.mem
        # The real BIOS routines set the VDP address and leave it after the
        # last byte, so later OUTs to the data port carry on from there.
        if name == 'WRTVRM':
            v.vram[hl & 0x3FFF] = r[A]
            v.addr = (hl + 1) & 0x3FFF; v.latch = None
        elif name == 'SETWRT':
            v.addr = hl & 0x3FFF; v.latch = None
        elif name == 'FILVRM':
            for i in range(bc):
                v.vram[(hl + i) & 0x3FFF] = r[A]
            v.addr = (hl + bc) & 0x3FFF; v.latch = None
        elif name == 'LDIRVM':
            for i in range(bc):
                v.vram[(de + i) & 0x3FFF] = m[(hl + i) & 0xFFFF]
            v.addr = (de + bc) & 0x3FFF; v.latch = None
            # On return HL holds the VRAM address (Konami's vuelca_tres_tercios
            # at 4964 depends on it); DE the source end; BC zero.
            src = (hl + bc) & 0xFFFF
            r[H], r[L] = de >> 8, de & 0xFF
            r[D], r[E] = src >> 8, src & 0xFF
            r[B] = r[C] = 0
        elif name == 'LDIRMV':
            for i in range(bc):
                m[(de + i) & 0xFFFF] = v.vram[(hl + i) & 0x3FFF]
            v.addr = (hl + bc) & 0x3FFF; v.latch = None
        elif name == 'WRTVDP':
            v.reg[r[C] & 7] = r[B]
        elif name == 'RDVDP':
            r[A] = v.read_status(); self.int_pending = False
        elif name == 'WRTPSG':
            self.psg[r[A] & 15] = r[E]
        elif name == 'RDPSG':
            r[A] = self.joy if r[A] == 14 else self.psg[r[A] & 15]
        elif name == 'SNSMAT':
            r[A] = self.keys[r[A]] if r[A] < len(self.keys) else 0xFF
        elif name == 'RSLREG':
            r[A] = 0
        elif name == 'RDSLT':
            r[A] = 0xFF                      # no second Konami cartridge
        # ENASLT: nothing to do in a flat memory model

    # --- running ------------------------------------------------------------
    def boot(self):
        init = self.mem[0x4002] | self.mem[0x4003] << 8
        sp = 0xF380 - 2
        self.mem[sp] = 0xFE; self.mem[sp + 1] = 0xFF   # return address FFFE
        self.mem[0xFFFE] = 0x18; self.mem[0xFFFF] = 0xFE  # JR $ (idle, interrupts drive the game)
        self.sim.registers[12] = sp
        self.sim.registers[24] = init
        self.sim.registers[27] = 1           # IM 1

    def run_frame(self):
        sim = self.sim; regs = sim.registers; mem = self.mem; ops = sim.opcodes
        end = self.next_int
        while regs[25] < end:
            pc = regs[24]
            if pc < 0x4000 and pc not in STUB_RANGE:
                raise Unknown('execution at %04X (unknown BIOS entry?) bank=%s' % (pc, mem.bank))
            ops[mem[pc]]()
            regs[25] += 1                    # MSX M1 wait state
            if self.int_pending and regs[26]:
                sim.accept_interrupt(regs, mem, pc)   # INT is level-triggered until status is read
            elif regs[28]:
                regs[25] = max(regs[25], end)         # HALT with nothing pending: idle to the frame end
        self.vdp.status |= 0x80              # frame flag
        self.int_pending = True
        self.next_int += FRAME_T
        self.frames += 1
