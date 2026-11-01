"""Run nemesis.sna in SkoolKit's 128K emulator (memory contention, AY
recorded) with scripted keys; report Konami's state and save screenshots.

usage: emu.py SECONDS [png_every_seconds] [prefix]
"""
import os as _os
NEM_ROOT = _os.environ.get('NEM_ROOT') or _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..'))  # the tree's root
import sys, os
sys.path.insert(0, NEM_ROOT + '/w31/tools')
from emu_bench import scr_png, FRAME
from skoolkit.snapshot import Snapshot
from skoolkit.simutils import from_snapshot
from skoolkit import CCMIOSimulator
from skoolkit.trace import Tracer

HERE = os.path.dirname(os.path.abspath(__file__))
KRAM = 0xAF00 - 0x8000          # Konami RAM offset in bank 2

def keys_default(f):
    kb = [0] * 8
    if (f // 25) % 4 == 0: kb[7] |= 1        # SPACE: start / fire
    return kb

# NEM_ALL=1 (all-stages runs of the checkers): the ship is invulnerable
# (la_nave_ha_muerto, MSX 1:75F0, returns at once) and, once play starts,
# Konami's own HYPER cheat and a second option are called (MSX 3:A0D8 and
# 3:A110, as lockstep_spec.py's HYPER=1 does on the MSX), so that keys_default
# play goes through every stage.
ALL = os.environ.get('NEM_ALL') == '1'
# NEM_TARGETS=1 (with NEM_ALL): the ship is put on every hidden target as it
# appears, so each is touched and the bonus stages (9-12) are played.
TARGETS = os.environ.get('NEM_TARGETS') == '1'
# NEM_MORTAL_BONUS=1 (with NEM_TARGETS): the ship can die once in each bonus
# stage; the life is given back.
MORTAL_BONUS = os.environ.get('NEM_MORTAL_BONUS') == '1'

def _syms(path):
    import re
    out = {}
    for l in open(path):
        mm = re.match(r'(\S+):\s+EQU\s+0x([0-9A-F]+)', l)
        if mm: out[mm.group(1)] = int(mm.group(2), 16) & 0xFFFF
    return out

class Spectrum:
    def __init__(self, path=os.path.join(HERE, 'nemesis.sna')):
        snap = Snapshot.get(path)
        if snap.type == 'SNA' and len(snap.tail) == 0xC000: snap.sp = (snap.sp + 2) % 65536
        self.sim = sim = from_snapshot(CCMIOSimulator, snap, {}, {'ay': [None] * 16},
                                       {'fast_djnz': False, 'fast_ldir': False})
        self.mem = sim.memory; self.mem.out7ffd(snap.out7ffd)
        self.tr = Tracer(sim, snap.border, snap.out7ffd, snap.outfffd, list(snap.ay), snap.outfe, False)
        sim.set_tracer(self.tr)
        self.regs = sim.registers; self.pc = snap.pc; self.frame = 0
        self.t0 = self.regs[25]
        self.hyper_done = False
        if ALL:
            sym = path[:-4] + '.sym'
            self.syms = _syms(sym if os.path.exists(sym) else os.path.join(HERE, 'nemesis.sym'))
            self.mem.banks[0][self.syms['m1_75F0'] - 0xC000] = 0xC9
    def hook(self, advance=False):
        """Per tick in NEM_ALL runs: the HYPER cheat once play has started.
        Call it where the program's stack is its own (the checkers' probe
        points); with advance, run on to the main loop's pm_tick first (at a
        frame boundary SP may be in use by the renderer)."""
        if MORTAL_BONUS and self.k(0xE000) == 5:
            b2 = self.mem.banks[2]; st = self.k(0xE061); lv = self.k(0xE060)
            if getattr(self, 'lives_was', None) is not None and lv < self.lives_was:
                self.died = getattr(self, 'died', set()) | {st}
                print('died in stage %d (t=%.1fs)' % (st, (self.regs[25] - self.t0) / 70908 / 50), flush=True)
                b2[0xE060 - 0xE000 + KRAM] = lv = self.lives_was
            self.lives_was = lv
            mortal = 9 <= st <= 12 and st not in getattr(self, 'died', set())
            self.mem.banks[0][self.syms['m1_75F0'] - 0xC000] = 0x00 if mortal else 0xC9
        if TARGETS and self.k(0xE000) == 5 and self.k(0xE1C1):
            b2 = self.mem.banks[2]
            b2[0xE204 - 0xE000 + KRAM] = self.k(0xE1C2); b2[0xE206 - 0xE000 + KRAM] = self.k(0xE1C3)
        if ALL and not self.hyper_done and self.k(0xE000) == 5:
            if advance:
                self.sim.trace(self.regs[24], self.syms['pm_tick'], 0, self.regs[25] + 70908 * 50, 1, None, None, None, None, None)
                self.pc = self.regs[24]
            self.call_konami(self.syms['m3_A0D8'], 4)
            self.call_konami(self.syms['m3_A110'], 4)
            self.hyper_done = True
    def call_konami(self, addr, page):
        """Run a Konami routine (in Spectrum page `page`) to its return, then
        put the program's PC, SP and paging back.  Paging is done by running
        set_page / out_page in the simulator (its OUT is what maps the bank)."""
        S = self.syms; regs = self.regs; b2 = self.mem.banks[2]
        saved = list(regs)                             # every register, put back at the end
        pc0, sp0, a0 = regs[24], regs[12], regs[0]
        cp0 = b2[S['cur_page'] - 0x8000]; pn0 = b2[S['port_now'] - 0x8000]
        def run(entry, a, ret_to=None):
            sp = regs[12] - 2; b2[sp - 0x8000] = 0x05; b2[sp + 1 - 0x8000] = 0x00     # returns to 0005
            if ret_to is not None:
                sp -= 2; b2[sp - 0x8000] = ret_to & 0xFF; b2[sp + 1 - 0x8000] = ret_to >> 8
            regs[12] = sp; regs[0] = a; regs[24] = entry
            self.sim.trace(entry, 0x0005, 0, regs[25] + 70908 * 200, 1, None, None, None, None, None)
            assert regs[24] == 0x0005, 'call to %04X did not return (PC %04X)' % (entry, regs[24])
            assert regs[12] == sp + (4 if ret_to is not None else 2), 'stack not balanced after %04X' % entry
        run(S['set_page'], page, ret_to=addr)          # set_page, then the routine
        run(S['set_page'], cp0)                        # Konami's page back
        if (pn0 & 7) != cp0: run(S['out_page'], pn0 & 7)   # a borrowed page back
        for i, v in enumerate(saved):
            if i != 25: regs[i] = v                    # (not the clock)

    def k(self, a):                       # Konami RAM byte at MSX address a
        return self.mem.banks[2][a - 0xE000 + KRAM]
    def run_frame(self, keys=keys_default):
        self.hook(advance=True)
        self.tr.keyboard = keys(self.frame)
        self.sim.trace(self.pc, -1, 0, self.t0 + (self.frame + 1) * FRAME, 1, None, None, None, None, None)
        self.pc = self.regs[24]; self.frame += 1
    def screen(self):
        return self.mem.banks[7 if self.tr.out7ffd & 8 else 5][:6912]

if __name__ == '__main__':
    secs = float(sys.argv[1]); every = float(sys.argv[2]) if len(sys.argv) > 2 else 0
    prefix = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, 'shots', 'f')
    os.makedirs(os.path.dirname(prefix), exist_ok=True)
    m = Spectrum()
    for f in range(int(secs * 50)):
        m.run_frame()
        if f % 50 == 49:
            print('t=%3ds PC=%04X page7ffd=%02X state=%d phase=%d ticks=%d dist=%04X' % (
                (f + 1) // 50, m.pc, m.tr.out7ffd, m.k(0xE000), m.k(0xE061), m.k(0xE003),
                m.k(0xE063) | m.k(0xE064) << 8), flush=True)
        if every and f % int(every * 50) == int(every * 50) - 1:
            scr_png(m.screen(), '%s_%04d.png' % (prefix, (f + 1) // 50 * 10 // 10))
