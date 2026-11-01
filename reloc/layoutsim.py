"""Step 4b: run the RELOCATED Konami code in a simulator with the Spectrum's
memory layout (fixed 4000-BFFF, paged C000 via port 7FFD) but the MSX hardware
model, side by side with the ORIGINAL ROM, and compare Konami RAM at the end of
every game tick.

Both runs: R-register reads pinned to the same deterministic sequence, input
keyed to the game's own tick counter (E003), and the ship made invulnerable by
patching la_nave_ha_muerto (0x75F0) to RET.
"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, re, bisect
sys.path.insert(0, NEM_ROOT + '/msxsim')
import msxsim
from msxsim import MSX, Memory, make_bios, FRAME_T

ROM = open(NEM_ROOT + '/nem.rom', 'rb').read()
RAM_DELTA = -0x3100
import os
INVULN = os.environ.get('NEM_DEATHS') != '1'   # NEM_DEATHS=1: the ship can die

def load_syms(path):
    s = {}
    for line in open(path):
        m = re.match(r'(\S+):\s+EQU\s+0x([0-9A-Fa-f]+)', line)
        if m: s[m.group(1)] = int(m.group(2), 16) & 0xFFFF
    return s

def pin_r(sim):
    regs = sim.registers
    state = [0x5A]
    def ld_a_r():
        state[0] = (state[0] * 73 + 41) & 0xFF
        a = state[0] & 0x7F
        regs[0] = a
        regs[1] = (a & 0xA8) + (a == 0) * 0x40 + regs[26] * 0x04 + (regs[1] % 2)
        regs[25] += 9
        regs[24] = (regs[24] + 2) % 65536
    sim.after_ED[0x5F] = ld_a_r

def keys_for_tick(t, started):
    """(keyboard row 8, joystick) for game tick t."""
    if not started:
        return 0xFE if (t % 40) < 4 else 0xFF, 0x3F
    return (0xFE if t % 8 < 4 else 0xFF), 0x3F

class KeyedMSX(MSX):
    """MSX whose SNSMAT/RDPSG answers depend on the game tick counter."""
    tick_addr = 0xE003
    def ram_at(self, a):
        return self.mem[a]
    def bios_call(self, pid, r):
        name = msxsim.NAMES[pid]
        if name in ('SNSMAT', 'RDPSG'):
            t = self.ram_at(self.tick_addr)
            started = self.ram_at(self.state_addr) == 5
            row8, joy = keys_for_tick(t, started)
            if name == 'SNSMAT':
                self.bios_calls[name] = self.bios_calls.get(name, 0) + 1
                r[0] = row8 if r[0] == 8 else 0xFF
                return
            if r[0] == 14:
                self.bios_calls[name] = self.bios_calls.get(name, 0) + 1
                r[0] = joy
                return
        MSX.bios_call(self, pid, r)

class Original(KeyedMSX):
    tick_addr = 0xE003; state_addr = 0xE000
    def __init__(self):
        rom = bytearray(ROM)
        if INVULN: rom[1 * 8192 + 0x75F0 - 0x6000] = 0xC9
        MSX.__init__(self, bytes(rom))
        pin_r(self.sim)
        self.tick_end = 0x4054
    def snapshot(self):
        return bytes(self.mem.ram[0xE000 - 0xC000:0xF100 - 0xC000])

class SpecMemory:
    """Spectrum 128K paging with the MSX BIOS-stub image as 'ROM'."""
    def __init__(self, bios, pages):
        self.bios = bios
        self.banks = pages              # dict n -> bytearray(16384)
        self.page = 0
        self.bank = [0, 0, 0, 0]        # for msxsim's error messages
    def __len__(self): return 0x10000
    def __getitem__(self, a):
        if a < 0x4000: return self.bios[a]
        if a < 0x8000: return self.banks[5][a - 0x4000]
        if a < 0xC000: return self.banks[2][a - 0x8000]
        return self.banks[self.page][a - 0xC000]
    def __setitem__(self, a, v):
        if a < 0x4000: return
        if a < 0x8000: self.banks[5][a - 0x4000] = v
        elif a < 0xC000: self.banks[2][a - 0x8000] = v
        else: self.banks[self.page][a - 0xC000] = v

class Relocated(KeyedMSX):
    tick_addr = 0xE003 + RAM_DELTA; state_addr = 0xE000 + RAM_DELTA
    def __init__(self, dirpath=NEM_ROOT + '/reloc'):
        self.syms = load_syms(dirpath + '/sim.sym')
        pages = {n: bytearray(16384) for n in range(9)}
        for n in (0, 1, 2, 3, 4, 5, 6, 8):
            pages[n][:] = open('%s/sim_page%d.bin' % (dirpath, n), 'rb').read()
        # Konami RAM starts zeroed, as in the MSX run.
        for a in range(0xAF00, 0xC000): pages[2][a - 0x8000] = 0
        bios = make_bios()
        # IM1 handler: call the relocated interrupcion instead of H.KEYI; no H.TIMI.
        h = 0x3F00 + 14
        assert bios[h] == 0xCD and bios[h + 1] == 0x9A and bios[h + 2] == 0xFD
        tgt = self.syms['m0_4028']
        bios[h:h + 6] = bytes([0xCD, tgt & 255, tgt >> 8, 0, 0, 0])
        MSX.__init__(self, ROM)                 # builds sim/VDP; memory replaced below
        self.mem = SpecMemory(bios, pages)
        from skoolkit.simulator import Simulator
        self.sim = Simulator(self.mem, {'SP': 0xAEF0})
        self.sim.set_tracer(self)
        pin_r(self.sim)
        # Invulnerability, same as the original run.
        a = self.syms['m1_75F0']
        self.mem.page = 0
        if INVULN: self.mem[a] = 0xC9
        # Idle loop for INIT's return.
        self.idle = self.syms['sim_idle']
        self.tick_end = self.syms['m0_4054']
    def write_port(self, registers, port, value, offset):
        if port == 0x7FFD:
            self.mem.page = value & 15     # sim only: page 8 is virtual
            return
        MSX.write_port(self, registers, port, value, offset)
    def boot(self):
        sp = 0xAEF0 - 2
        self.mem[sp] = self.idle & 255; self.mem[sp + 1] = self.idle >> 8
        self.sim.registers[12] = sp
        self.sim.registers[24] = self.syms['m0_4071']
        self.sim.registers[27] = 1
    def snapshot(self):
        return bytes(self.mem.banks[2][0xAF00 - 0x8000:0xC000 - 0x8000])

def run_ticks(m, n_ticks, on_tick):
    """Run until n_ticks game ticks have completed, calling on_tick(i, m)."""
    regs = m.sim.registers; ops = m.sim.opcodes; mem = m.mem; sim = m.sim
    done = 0; stop = m.tick_end
    while done < n_ticks:
        end = m.next_int
        while regs[25] < end:
            pc = regs[24]
            if pc == stop:
                on_tick(done, m); done += 1
                if done >= n_ticks: return
            if pc < 0x4000 and pc not in msxsim.STUB_RANGE:
                raise msxsim.Unknown('execution at %04X' % pc)
            ops[mem[pc]]()
            regs[25] += 1
            if m.int_pending and regs[26]:
                sim.accept_interrupt(regs, mem, pc)
            elif regs[28]:
                regs[25] = max(regs[25], end)
        m.vdp.status |= 0x80; m.int_pending = True; m.next_int += FRAME_T; m.frames += 1


# --- relocation-aware comparison ------------------------------------------
import sys as _s
_s.path.insert(0, NEM_ROOT + '/reloc')
import gen as _gen

class Mapper:
    """Translate an original 16-bit value into every relocated value it could be."""
    def __init__(self, syms):
        self.lab = {}
        for k, v in syms.items():
            m = re.match(r'm(\d+)_([0-9A-F]{4})$', k)
            if m: self.lab.setdefault(int(m.group(1)), {})[int(m.group(2), 16)] = v
        self.keys = {b: sorted(d) for b, d in self.lab.items()}
    def cands(self, w):
        out = set()
        if 0xE000 <= w <= 0xF0FF: out.add(w + RAM_DELTA)
        for b, org in ((0, 0x4000), (1, 0x6000), (2, 0x8000), (3, 0xA000), (7, 0x8000)):
            if org <= w < org + 0x2000 and b in self.keys:
                ks = self.keys[b]; i = bisect.bisect_right(ks, w) - 1
                if i >= 0: out.add((self.lab[b][ks[i]] + w - ks[i]) & 0xFFFF)
        for b, (sec, base, org) in _gen.DATA_PLACE.items():
            if org <= w < org + 0x2000: out.add(_gen.place_data(b, w))
            for lo, hi, psec, pbase in _gen.DATA_PIECES.get(b, ()):
                if w == hi: out.add(pbase + hi - lo)     # a pointer just past a piece (a script read to its end)
        return out

def explain(a, b, mp):
    """Byte positions of a/b that differ and are not explained as relocated words."""
    bad = []
    n = len(a); k = 0
    diffs = [i for i in range(n) if a[i] != b[i]]
    ok = set()
    for i in diffs:
        if i in ok: continue
        for j in (i - 1, i):
            if 0 <= j < n - 1:
                wa = a[j] | a[j + 1] << 8; wb = b[j] | b[j + 1] << 8
                if wb in mp.cands(wa):
                    ok.add(j); ok.add(j + 1); break
        else:
            bad.append(i)
    return bad

# --- schedule independent of CPU speed -----------------------------------
# The relocated code is slower (far stubs, paging calls), so with real frame
# timing the two machines would take interrupts at different points.  For
# equivalence testing both run on a virtual clock that counts only Konami
# instructions (original ROM instructions / relocated item starts; BIOS stubs,
# DCOMPR, far stubs and paging helpers are free), with an interrupt every
# VFRAME counted instructions.  Same behaviour => same interrupt points.

def idle_addr(m):
    return 0xFFFE if isinstance(m, Original) else m.idle

CALL_OPS = {0xCD, 0xC4, 0xCC, 0xD4, 0xDC, 0xE4, 0xEC, 0xF4, 0xFC, 0xE7}
VFRAME = 1500         # counted calls and loop heads per virtual frame

_items_cache = []
def call_items():
    """(bank, addr) of listing items that are CALL/RST 20h instructions.  Only
    these advance the virtual clock: both layouts execute exactly the same
    calls, while straight-line counts differ where address arithmetic carries
    differently or where the relocated code expands an instruction."""
    if not _items_cache:
        import gen as G
        g = G.Gen(ROM); out = set()
        for b in g.items:
            org = G.ORG[b]; raw = g.raw[b]
            for it in g.items[b]:
                if it[2] != 'code': continue
                a = it[0]; op = raw[a - org]
                if op in CALL_OPS: out.add((b, a))
                # loop heads: targets of backward relative / absolute jumps in the same bank
                t = None
                if op in (0x10, 0x18, 0x20, 0x28, 0x30, 0x38):
                    d = raw[a - org + 1]; t = a + 2 + (d - 256 if d > 127 else d)
                elif op in (0xC3, 0xC2, 0xCA, 0xD2, 0xDA, 0xE2, 0xEA, 0xF2, 0xFA) and it[1] == 3:
                    t = raw[a - org + 1] | raw[a - org + 2] << 8
                if t is not None and org <= t <= a and (b, t) in g.home:
                    out.add((b, t))
        _items_cache.append((g, out))
    return _items_cache[0]

_counted_cache = {}
def counted_sets(m):
    """Relocated addresses of the call items: (fixed set, {page: set})."""
    key = id(m.syms)
    if key in _counted_cache: return _counted_cache[key]
    g, calls = call_items()
    pagenum = {'A': 0, 'B': 3, 'C': 4, 'D': 6, 'E': 1, 'F': 8}
    fixed = set(); paged = {}
    for k, v in m.syms.items():
        mm = re.match(r'(?:([A-Z])_)?m(\d+)_([0-9A-F]{4})$', k)
        if not mm: continue
        b = int(mm.group(2)); a = int(mm.group(3), 16)
        if (b, a) not in calls: continue
        sec = mm.group(1) or g.home[(b, a)]
        if v < 0xC000: fixed.add(v)
        else: paged.setdefault(pagenum[sec], set()).add(v)
    _counted_cache[key] = (fixed, paged)
    return fixed, paged

def vclock_tick(m, rec=None, conv=None):
    """Run to the end of the next game tick on the virtual clock."""
    regs = m.sim.registers; ops = m.sim.opcodes; mem = m.mem; sim = m.sim
    stop = m.tick_end; idle = idle_addr(m)
    orig = isinstance(m, Original)
    if not orig: fixed, paged = counted_sets(m)
    else: home = call_items()[1]
    if not hasattr(m, 'vcount'): m.vcount = 0
    first = True; f0 = m.frames
    while True:
        pc = regs[24]
        if pc == stop and not first:
            return
        first = False
        if orig:
            if pc < 0x6000: counted = pc == idle or (0x4000 <= pc and (0, pc) in home)
            elif pc < 0xC000: counted = (mem.bank[(pc - 0x4000) >> 13], pc) in home
            else: counted = pc == idle
        else:
            counted = pc == idle or (pc in fixed if pc < 0xC000 else pc in paged.get(mem.page, ()))
        if counted:
            m.vcount += 1
            if m.vcount >= VFRAME:
                m.vcount = 0
                m.vdp.status |= 0x80; m.int_pending = True; m.frames += 1
                if m.frames - f0 > 400: raise RuntimeError('stall: no tick end for 400 frames, PC=%04X' % pc)
        if pc < 0x4000 and pc not in msxsim.STUB_RANGE:
            raise msxsim.Unknown('execution at %04X' % pc)
        if rec is not None:
            c = conv(m, pc)
            if c is not None: rec.append(c)
        ops[mem[pc]]()
        regs[25] += 1
        if m.int_pending and regs[26]:
            sim.accept_interrupt(regs, mem, pc)
        if regs[28]: raise RuntimeError('HALT at %04X' % pc)
